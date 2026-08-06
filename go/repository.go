package main

import "context"

// Mirrors org.acme.repository.FruitRepository (a Panache PanacheRepository[Fruit]).
//
// Two implementations exist, selected by the QUERY_MODE environment variable - see main.go. This
// mirrors the Node.js module's QUERY_MODE experiment (nodejs/src/repository/fruit.repository.ts),
// which found the raw-SQL path roughly 1.7x the throughput of the ORM path there. Reproducing
// both here answers the same question for Go/GORM specifically.
type FruitRepository interface {
	ListAll(ctx context.Context) ([]FruitDto, error)
	FindByName(ctx context.Context, name string) (*FruitDto, error)
	Persist(ctx context.Context, req CreateFruitRequest) (FruitDto, error)
}
