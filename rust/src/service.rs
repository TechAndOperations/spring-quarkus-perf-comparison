use std::sync::Arc;

use tracing::instrument;

use crate::dto::{CreateFruitRequest, FruitDto};
use crate::repository::FruitRepository;

/// Mirrors `org.acme.service.FruitService`. `#[instrument]` is the `tracing` equivalent of the
/// Java service's `@WithSpan` annotations. Holds a trait object rather than a concrete
/// repository type so `main.rs` can select the ORM or SQL implementation at startup based on
/// QUERY_MODE.
#[derive(Clone)]
pub struct FruitService {
    repository: Arc<dyn FruitRepository>,
}

impl FruitService {
    pub fn new(repository: Arc<dyn FruitRepository>) -> Self {
        Self { repository }
    }

    #[instrument(name = "FruitService.getAllFruits", skip(self))]
    pub async fn get_all_fruits(&self) -> anyhow::Result<Vec<FruitDto>> {
        self.repository.list_all().await
    }

    #[instrument(name = "FruitService.getFruitByName", skip(self))]
    pub async fn get_fruit_by_name(&self, name: &str) -> anyhow::Result<Option<FruitDto>> {
        self.repository.find_by_name(name).await
    }

    #[instrument(name = "FruitService.createFruit", skip(self))]
    pub async fn create_fruit(&self, fruit: CreateFruitRequest) -> anyhow::Result<FruitDto> {
        self.repository.persist(fruit).await
    }
}
