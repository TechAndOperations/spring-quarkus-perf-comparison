package main

import (
	"context"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
)

var tracer = otel.Tracer("go")

// Mirrors org.acme.service.FruitService. tracer.Start is the tracing equivalent of the Java
// service's @WithSpan annotations.
type FruitService struct {
	repository FruitRepository
}

func newFruitService(repository FruitRepository) *FruitService {
	return &FruitService{repository: repository}
}

func (s *FruitService) GetAllFruits(ctx context.Context) ([]FruitDto, error) {
	ctx, span := tracer.Start(ctx, "FruitService.getAllFruits")
	defer span.End()

	return s.repository.ListAll(ctx)
}

func (s *FruitService) GetFruitByName(ctx context.Context, name string) (*FruitDto, error) {
	ctx, span := tracer.Start(ctx, "FruitService.getFruitByName")
	defer span.End()

	span.SetAttributes(attribute.String("arg.name", name))

	return s.repository.FindByName(ctx, name)
}

func (s *FruitService) CreateFruit(ctx context.Context, req CreateFruitRequest) (FruitDto, error) {
	ctx, span := tracer.Start(ctx, "FruitService.createFruit")
	defer span.End()

	return s.repository.Persist(ctx, req)
}
