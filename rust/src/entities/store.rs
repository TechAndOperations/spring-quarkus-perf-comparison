use sea_orm::entity::prelude::*;

/// Mirrors `org.acme.domain.Store` (`@Entity`, `@Cacheable`). Same sequence-based id caveat as
/// `fruit::Model`. `address`/`city`/`country` are flat columns here - see `entities/mod.rs` for
/// why SeaORM has no embedded-value-object equivalent of the Java `Address` `@Embeddable`.
#[derive(Clone, Debug, PartialEq, DeriveEntityModel)]
#[sea_orm(table_name = "stores")]
pub struct Model {
    #[sea_orm(primary_key, auto_increment = false)]
    pub id: i64,
    pub name: String,
    pub currency: String,
    pub address: String,
    pub city: String,
    pub country: String,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(has_many = "super::store_fruit_price::Entity")]
    StoreFruitPrice,
}

impl Related<super::store_fruit_price::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::StoreFruitPrice.def()
    }
}

impl ActiveModelBehavior for ActiveModel {}
