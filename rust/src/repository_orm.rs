use async_trait::async_trait;
use sea_orm::{ColumnTrait, ConnectionTrait, DatabaseBackend, DatabaseConnection, EntityTrait, QueryFilter, Statement};
use std::collections::HashMap;

use crate::dto::{AddressDto, CreateFruitRequest, FruitDto, StoreDto, StoreFruitPriceDto};
use crate::entities::{fruit, store, store_fruit_price};
use crate::repository::FruitRepository;

/// `QUERY_MODE=orm` (the default). SeaORM entities + relation loading, the structural analogue
/// of quarkus3-virtual's Hibernate relations, the Node.js module's TypeORM path, and
/// go-orm.
///
/// Loading strategy: one query for the fruits, one query for all `store_fruit_prices` joined to
/// their `store` (via `find_also_related`, which - like TypeORM's `find({ relations })` and
/// unlike GORM's `Preload` - does emit a single JOIN for that pair), then the prices are grouped
/// by `fruit_id` in application code and attached to their fruit. This mirrors the row-grouping
/// already done by hand in the raw-SQL path (`repository_sql.rs::group_fruit_rows`) and the
/// Node.js module's `groupFruitRows` - the grouping step is unavoidable either way because no
/// single SeaORM call eager-loads a two-level relation (fruit -> price -> store) in one shot.
pub struct OrmFruitRepository {
    db: DatabaseConnection,
}

impl OrmFruitRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    /// Loads every store_fruit_price joined to its store, grouped by fruit_id. Shared by
    /// `list_all` (no filter) and `find_by_name` (filtered to one fruit's id).
    async fn load_prices_by_fruit(
        &self,
        fruit_id_filter: Option<i64>,
    ) -> anyhow::Result<HashMap<i64, Vec<StoreFruitPriceDto>>> {
        let mut query = store_fruit_price::Entity::find();

        if let Some(fruit_id) = fruit_id_filter {
            query = query.filter(store_fruit_price::Column::FruitId.eq(fruit_id));
        }

        let pairs = query.find_also_related(store::Entity).all(&self.db).await?;

        let mut by_fruit: HashMap<i64, Vec<StoreFruitPriceDto>> = HashMap::new();

        for (price, store) in pairs {
            // LEFT JOIN semantics: a price row with no matching store would come back as None -
            // in practice this never happens because store_id has a NOT NULL FK, but skipping a
            // None here (instead of unwrapping) keeps this path from panicking if that ever
            // changes rather than mirroring a case that cannot occur.
            if let Some(store) = store {
                by_fruit.entry(price.fruit_id).or_default().push(StoreFruitPriceDto {
                    store: StoreDto {
                        id: store.id,
                        name: store.name,
                        currency: store.currency,
                        address: AddressDto { address: store.address, city: store.city, country: store.country },
                    },
                    price: price.price,
                });
            }
        }

        Ok(by_fruit)
    }

    fn to_dto(model: fruit::Model, prices_by_fruit: &mut HashMap<i64, Vec<StoreFruitPriceDto>>) -> FruitDto {
        FruitDto {
            id: model.id,
            name: model.name,
            description: model.description,
            store_prices: prices_by_fruit.remove(&model.id).unwrap_or_default(),
        }
    }
}

#[async_trait]
impl FruitRepository for OrmFruitRepository {
    /// Panache `listAll()` - no ORDER BY, matching the raw-SQL implementation and the Java
    /// module.
    async fn list_all(&self) -> anyhow::Result<Vec<FruitDto>> {
        let fruits = fruit::Entity::find().all(&self.db).await?;
        let mut prices_by_fruit = self.load_prices_by_fruit(None).await?;

        Ok(fruits.into_iter().map(|model| Self::to_dto(model, &mut prices_by_fruit)).collect())
    }

    async fn find_by_name(&self, name: &str) -> anyhow::Result<Option<FruitDto>> {
        let Some(model) = fruit::Entity::find().filter(fruit::Column::Name.eq(name)).one(&self.db).await? else {
            return Ok(None);
        };

        let mut prices_by_fruit = self.load_prices_by_fruit(Some(model.id)).await?;

        Ok(Some(Self::to_dto(model, &mut prices_by_fruit)))
    }

    /// `fruits.id` has no DEFAULT in `scripts/dbdata/db.sql` (Hibernate's
    /// `GenerationType.SEQUENCE` draws it from `fruits_seq`), and SeaORM - like GORM and the
    /// raw-SQL path - has no equivalent of Hibernate's `@SequenceGenerator`, so the `nextval()`
    /// call is manual here too, regardless of which implementation is used.
    async fn persist(&self, req: CreateFruitRequest) -> anyhow::Result<FruitDto> {
        let row = self
            .db
            .query_one(Statement::from_string(DatabaseBackend::Postgres, "SELECT nextval('fruits_seq') AS id"))
            .await?
            .ok_or_else(|| anyhow::anyhow!("nextval('fruits_seq') returned no row"))?;

        let id: i64 = row.try_get("", "id")?;

        let active_model = fruit::ActiveModel {
            id: sea_orm::ActiveValue::Set(id),
            name: sea_orm::ActiveValue::Set(req.name.clone()),
            description: sea_orm::ActiveValue::Set(req.description.clone()),
        };

        fruit::Entity::insert(active_model).exec(&self.db).await?;

        Ok(FruitDto { id, name: req.name, description: req.description, store_prices: Vec::new() })
    }
}
