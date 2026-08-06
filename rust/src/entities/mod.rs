//! SeaORM entities, used only in QUERY_MODE=orm. Mirror the JPA entities in
//! quarkus3-virtual/src/main/java/org/acme/domain/, the TypeORM entities in
//! nodejs/src/domain/, and the GORM entities in go/entities_gorm.go - this is the Rust
//! analogue of the "idiomatic ORM path" question already explored for those two modules.
//!
//! Unlike JPA's `@Embeddable`/TypeORM's `{ prefix: false }`/GORM's `embedded` tag, SeaORM has no
//! embedded-value-object concept: there is no separate `Address` entity here, the `address`/
//! `city`/`country` columns are just flat fields directly on `store::Model` - the DTO layer
//! (dto.rs) is what reassembles them into a nested `AddressDto` on the way out.

pub mod fruit;
pub mod store;
pub mod store_fruit_price;
