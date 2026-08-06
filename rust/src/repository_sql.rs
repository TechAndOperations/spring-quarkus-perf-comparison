use async_trait::async_trait;
use sqlx::PgPool;
use std::collections::HashMap;

use crate::dto::{AddressDto, CreateFruitRequest, FruitDto, StoreDto, StoreFruitPriceDto};
use crate::repository::FruitRepository;

/// `QUERY_MODE=sql`. Single hand-written join, no ORM/entity hydration - the query shape
/// validated in the Node.js module (see nodejs/src/repository/fruit-rows.ts, "Two query
/// implementations"), where it roughly doubled throughput over TypeORM's `find({ relations })`,
/// and the same shape as go-sql.
///
/// `price::float8` casts Postgres `numeric` to `f64` at the database, avoiding a bignum/decimal
/// dependency; matches the Node.js module's coercion of the same column
/// (see nodejs/src/domain/numeric.transformer.ts) and Java's `BigDecimal` -> JSON number.
///
/// No ORDER BY, matching quarkus3-virtual's `FruitRepository.listAll()` (Panache `listAll()`).
const FRUIT_ROWS_SELECT: &str = "
    SELECT f.id            AS f_id,
           f.name          AS f_name,
           f.description   AS f_description,
           p.price::float8 AS p_price,
           s.id            AS s_id,
           s.name          AS s_name,
           s.currency      AS s_currency,
           s.address       AS s_address,
           s.city          AS s_city,
           s.country       AS s_country
      FROM fruits f
      LEFT JOIN store_fruit_prices p ON p.fruit_id = f.id
      LEFT JOIN stores s              ON s.id = p.store_id";

#[derive(sqlx::FromRow)]
struct FruitRow {
    f_id: i64,
    f_name: String,
    f_description: Option<String>,
    p_price: Option<f64>,
    s_id: Option<i64>,
    s_name: Option<String>,
    s_currency: Option<String>,
    s_address: Option<String>,
    s_city: Option<String>,
    s_country: Option<String>,
}

/// Collapses the flat join result into fruit-shaped DTOs, preserving first-appearance order (a
/// `HashMap` plus an order-preserving `Vec` - Rust's `HashMap` does not iterate in insertion
/// order, unlike JavaScript's `Map`, which the Node.js `groupFruitRows` relies on directly).
fn group_fruit_rows(rows: Vec<FruitRow>) -> Vec<FruitDto> {
    let mut order: Vec<i64> = Vec::new();
    let mut by_id: HashMap<i64, FruitDto> = HashMap::new();

    for row in rows {
        let fruit = by_id.entry(row.f_id).or_insert_with(|| {
            order.push(row.f_id);

            FruitDto {
                id: row.f_id,
                name: row.f_name.clone(),
                description: row.f_description.clone(),
                store_prices: Vec::new(),
            }
        });

        // LEFT JOIN: a fruit with no prices yields one row with every p_/s_ column null.
        if let (Some(price), Some(store_id), Some(store_name), Some(currency), Some(address), Some(city), Some(country)) =
            (row.p_price, row.s_id, row.s_name, row.s_currency, row.s_address, row.s_city, row.s_country)
        {
            fruit.store_prices.push(StoreFruitPriceDto {
                store: StoreDto {
                    id: store_id,
                    name: store_name,
                    currency,
                    address: AddressDto { address, city, country },
                },
                price,
            });
        }
    }

    order.into_iter().filter_map(|id| by_id.remove(&id)).collect()
}

pub struct SqlFruitRepository {
    pool: PgPool,
}

impl SqlFruitRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl FruitRepository for SqlFruitRepository {
    async fn list_all(&self) -> anyhow::Result<Vec<FruitDto>> {
        let rows: Vec<FruitRow> = sqlx::query_as(FRUIT_ROWS_SELECT).fetch_all(&self.pool).await?;

        Ok(group_fruit_rows(rows))
    }

    async fn find_by_name(&self, name: &str) -> anyhow::Result<Option<FruitDto>> {
        let sql = format!("{FRUIT_ROWS_SELECT} WHERE f.name = $1");
        let rows: Vec<FruitRow> = sqlx::query_as(&sql).bind(name).fetch_all(&self.pool).await?;

        Ok(group_fruit_rows(rows).into_iter().next())
    }

    /// `fruits.id` has no DEFAULT in `scripts/dbdata/db.sql`, so the id is drawn from the
    /// `fruits_seq` sequence in the same statement as the insert - one round trip, matching
    /// Hibernate's `GenerationType.SEQUENCE` with `allocationSize = 1` in effect (one `nextval`
    /// per row) without its two-statement mechanics.
    async fn persist(&self, fruit: CreateFruitRequest) -> anyhow::Result<FruitDto> {
        let id: i64 = sqlx::query_scalar(
            "INSERT INTO fruits (id, name, description) VALUES (nextval('fruits_seq'), $1, $2) RETURNING id",
        )
        .bind(&fruit.name)
        .bind(&fruit.description)
        .fetch_one(&self.pool)
        .await?;

        Ok(FruitDto {
            id,
            name: fruit.name,
            description: fruit.description,
            store_prices: Vec::new(),
        })
    }
}
