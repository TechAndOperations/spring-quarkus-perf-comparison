use async_trait::async_trait;

use crate::dto::{CreateFruitRequest, FruitDto};

/// Mirrors `org.acme.repository.FruitRepository` (a Panache `PanacheRepository<Fruit>`).
///
/// Two implementations exist, selected by the QUERY_MODE environment variable (default "orm") -
/// see main.rs:
///  - `repository_orm.rs` - SeaORM entities + relation loading, the structural analogue of
///    quarkus3-virtual's Hibernate relations, the Node.js module's TypeORM path, and
///    go-orm.
///  - `repository_sql.rs` - a single hand-written join, no entity hydration, the same shape as
///    the Node.js module's faster "sql" mode and go-sql.
///
/// This mirrors the same ORM-vs-raw-SQL experiment already run for the other two non-JVM
/// modules (nodejs's QUERY_MODE; go-sql/go-orm as separate pipeline runtimes).
///
/// `async_trait` boxes the futures returned by these methods: native `async fn` in traits is not
/// yet dyn-compatible, and `main.rs` needs to select an implementation at runtime behind
/// `Arc<dyn FruitRepository>`, which native async-fn-in-traits cannot do without this crate.
#[async_trait]
pub trait FruitRepository: Send + Sync {
    /// Panache `listAll()`.
    async fn list_all(&self) -> anyhow::Result<Vec<FruitDto>>;

    /// Panache `find("name", name).firstResultOptional()`.
    async fn find_by_name(&self, name: &str) -> anyhow::Result<Option<FruitDto>>;

    /// Panache `persist()`. Deliberately maps only `name` and `description`, matching
    /// `FruitMapper.map(FruitDTO -> Fruit)`'s comment: "the rest of the relationships aren't
    /// built out yet" - `store_prices` is therefore always empty on the returned DTO in both
    /// implementations.
    async fn persist(&self, fruit: CreateFruitRequest) -> anyhow::Result<FruitDto>;
}
