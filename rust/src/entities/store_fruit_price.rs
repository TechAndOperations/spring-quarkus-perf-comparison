use sea_orm::entity::prelude::*;

/// Mirrors `org.acme.domain.StoreFruitPrice`. The Java entity uses an `@EmbeddedId`
/// (`StoreFruitPriceId`) with `@MapsId`; SeaORM has no embedded-id equivalent, so the composite
/// key is expressed as two `primary_key`-tagged columns - the same pattern used by the pgx/GORM
/// repositories in this repo's other modules (`repository_pgx.go`, `entities_gorm.go`). PK is
/// `(fruit_id, store_id)` per `scripts/dbdata/db.sql`.
#[derive(Clone, Debug, PartialEq, DeriveEntityModel)]
#[sea_orm(table_name = "store_fruit_prices")]
pub struct Model {
    #[sea_orm(primary_key, auto_increment = false, column_name = "fruit_id")]
    pub fruit_id: i64,
    #[sea_orm(primary_key, auto_increment = false, column_name = "store_id")]
    pub store_id: i64,
    // `numeric(12,2)` in the DB - `f64` would fail to decode at runtime (sqlx's `Decode<Postgres>
    // for f64` only accepts the FLOAT8 OID). Converted to `f64` for the DTO in repository_orm.rs.
    pub price: Decimal,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(belongs_to = "super::fruit::Entity", from = "Column::FruitId", to = "super::fruit::Column::Id")]
    Fruit,
    #[sea_orm(belongs_to = "super::store::Entity", from = "Column::StoreId", to = "super::store::Column::Id")]
    Store,
}

impl Related<super::fruit::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Fruit.def()
    }
}

impl Related<super::store::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Store.def()
    }
}

impl ActiveModelBehavior for ActiveModel {}
