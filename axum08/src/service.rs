use tracing::instrument;

use crate::dto::{CreateFruitRequest, FruitDto};
use crate::repository::FruitRepository;

/// Mirrors `org.acme.service.FruitService`. `#[instrument]` is the `tracing` equivalent of the
/// Java service's `@WithSpan` annotations.
#[derive(Clone)]
pub struct FruitService {
    repository: FruitRepository,
}

impl FruitService {
    pub fn new(repository: FruitRepository) -> Self {
        Self { repository }
    }

    #[instrument(name = "FruitService.getAllFruits", skip(self))]
    pub async fn get_all_fruits(&self) -> Result<Vec<FruitDto>, sqlx::Error> {
        self.repository.list_all().await
    }

    #[instrument(name = "FruitService.getFruitByName", skip(self))]
    pub async fn get_fruit_by_name(&self, name: &str) -> Result<Option<FruitDto>, sqlx::Error> {
        self.repository.find_by_name(name).await
    }

    #[instrument(name = "FruitService.createFruit", skip(self))]
    pub async fn create_fruit(&self, fruit: CreateFruitRequest) -> Result<FruitDto, sqlx::Error> {
        self.repository.persist(fruit).await
    }
}
