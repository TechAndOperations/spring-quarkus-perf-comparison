use sea_orm::entity::prelude::*;

/// Mirrors `org.acme.domain.Fruit`. `id` has no DEFAULT in `scripts/dbdata/db.sql` (Hibernate's
/// `GenerationType.SEQUENCE` draws it from `fruits_seq`), so `auto_increment = false` and the
/// repository must supply it explicitly - see `repository_orm.rs::persist`.
#[derive(Clone, Debug, PartialEq, DeriveEntityModel)]
#[sea_orm(table_name = "fruits")]
pub struct Model {
    #[sea_orm(primary_key, auto_increment = false)]
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
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
