use serde::{Deserialize, Serialize};

/// Mirrors `org.acme.dto.AddressDTO`. Field order matches the Java record's declaration order,
/// same convention used by the Node.js module (see nodejs/src/dto/address.dto.ts) - both differ
/// harmlessly from quarkus3-virtual's alphabetical order (its Jackson reflection-free serializers
/// sort keys; see nodejs/README.md, "JSON key order differs ... harmlessly").
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddressDto {
    pub address: String,
    pub city: String,
    pub country: String,
}

/// Mirrors `org.acme.dto.StoreDTO`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoreDto {
    pub id: i64,
    pub name: String,
    pub currency: String,
    pub address: AddressDto,
}

/// Mirrors `org.acme.dto.StoreFruitPriceDTO`. `price` is never omitted even when zero - it is not
/// "empty" for Jackson's NON_EMPTY inclusion, only null/blank/empty-collection values are.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoreFruitPriceDto {
    pub store: StoreDto,
    pub price: f64,
}

/// Mirrors `org.acme.dto.FruitDTO`.
///
/// `description` and `store_prices` are skipped when empty to replicate
/// `quarkus.jackson.serialization-inclusion: non-empty` from
/// `quarkus3-virtual/src/main/resources/application.yml` - the same rule the Node.js module
/// implements in its mappers (see nodejs/src/mapping/fruit.mapper.ts).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FruitDto {
    pub id: i64,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub store_prices: Vec<StoreFruitPriceDto>,
}

/// Request body for `POST /fruits`. Only `name` and `description` are accepted - the Java
/// mapper's `FruitMapper.map(FruitDTO -> Fruit)` deliberately maps only these two fields
/// ("the rest of the relationships aren't built out yet"), and both the Node.js and this
/// implementation preserve that on purpose. `id`/`storePrices` sent by a client are ignored.
#[derive(Debug, Clone, Deserialize)]
pub struct CreateFruitRequest {
    pub name: String,
    pub description: Option<String>,
}
