package main

import (
	"context"

	"gorm.io/gorm"
)

// GORM's idiomatic eager-loading is Preload, which issues one query per relation level (Fruits,
// then StorePrices+Store) rather than a single JOIN - a genuine difference from the TypeORM
// module's find({ relations }), which does emit one JOIN. Both are each ORM's own idiomatic
// default, not a bug; see go/README.md for the comparative note this produces.
type gormFruitRepository struct {
	db *gorm.DB
}

func newGormFruitRepository(db *gorm.DB) *gormFruitRepository {
	return &gormFruitRepository{db: db}
}

func toFruitDto(entity GormFruit) FruitDto {
	dto := FruitDto{ID: entity.ID, Name: entity.Name, Description: entity.Description}

	for _, price := range entity.StorePrices {
		dto.StorePrices = append(dto.StorePrices, StoreFruitPriceDto{
			Store: StoreDto{
				ID:       price.Store.ID,
				Name:     price.Store.Name,
				Currency: price.Store.Currency,
				Address: AddressDto{
					Address: price.Store.Address.Address,
					City:    price.Store.Address.City,
					Country: price.Store.Address.Country,
				},
			},
			Price: price.Price,
		})
	}

	return dto
}

// Panache listAll().
func (r *gormFruitRepository) ListAll(ctx context.Context) ([]FruitDto, error) {
	var entities []GormFruit

	if err := r.db.WithContext(ctx).Preload("StorePrices.Store").Find(&entities).Error; err != nil {
		return nil, err
	}

	dtos := make([]FruitDto, 0, len(entities))
	for _, entity := range entities {
		dtos = append(dtos, toFruitDto(entity))
	}

	return dtos, nil
}

// Panache find("name", name).firstResultOptional().
func (r *gormFruitRepository) FindByName(ctx context.Context, name string) (*FruitDto, error) {
	var entity GormFruit

	err := r.db.WithContext(ctx).Preload("StorePrices.Store").Where("name = ?", name).First(&entity).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}

		return nil, err
	}

	dto := toFruitDto(entity)

	return &dto, nil
}

// Panache persist(). Same sequence-based id generation as the pgx implementation - GORM has no
// equivalent of Hibernate's @SequenceGenerator, so the nextval() call is manual here too,
// regardless of which Go implementation is used.
//
// Deliberately maps only Name and Description, matching FruitMapper.map(FruitDTO -> Fruit)'s
// comment: "the rest of the relationships aren't built out yet".
func (r *gormFruitRepository) Persist(ctx context.Context, req CreateFruitRequest) (FruitDto, error) {
	var id int64
	if err := r.db.WithContext(ctx).Raw("SELECT nextval('fruits_seq')").Scan(&id).Error; err != nil {
		return FruitDto{}, err
	}

	description := ""
	if req.Description != nil {
		description = *req.Description
	}

	entity := GormFruit{ID: id, Name: req.Name, Description: description}

	if err := r.db.WithContext(ctx).Create(&entity).Error; err != nil {
		return FruitDto{}, err
	}

	return FruitDto{ID: entity.ID, Name: entity.Name, Description: entity.Description}, nil
}
