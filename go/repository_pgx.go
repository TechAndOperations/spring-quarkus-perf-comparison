package main

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Single hand-written join, no ORM/entity hydration - the same query shape used by the Rust
// module (rust/src/repository.rs) and the Node.js module's "sql" query mode
// (nodejs/src/repository/fruit-rows.ts), where it roughly doubled throughput over TypeORM's
// find({ relations }).
//
// price::float8 casts Postgres numeric to float64 at the database, avoiding a bignum/decimal
// dependency; matches Java's BigDecimal -> JSON number and the other two modules' equivalent
// coercion.
//
// No ORDER BY, matching quarkus3-virtual's FruitRepository.listAll() (Panache listAll()).
const fruitRowsSelect = `
	SELECT f.id            AS f_id,
	       f.name          AS f_name,
	       f.description   AS f_description,
	       p.price::float8 AS p_price,
	       s.id            AS s_id,
	       s.name          AS s_name,
	       s.currency      AS s_currency,
	       s.address       AS s_address,
	       s.city          AS s_city,
	       s.country       AS s_country
	  FROM fruits f
	  LEFT JOIN store_fruit_prices p ON p.fruit_id = f.id
	  LEFT JOIN stores s              ON s.id = p.store_id`

type fruitRow struct {
	fruitID     int64
	fruitName   string
	description *string
	price       *float64
	storeID     *int64
	storeName   *string
	currency    *string
	address     *string
	city        *string
	country     *string
}

// Collapses the flat join result into fruit-shaped DTOs, preserving first-appearance order via a
// separate order slice - Go maps, like Rust's HashMap and unlike JavaScript's Map, do not iterate
// in insertion order.
func groupFruitRows(rows []fruitRow) []FruitDto {
	order := make([]int64, 0)
	byID := make(map[int64]*FruitDto)

	for _, row := range rows {
		fruit, ok := byID[row.fruitID]
		if !ok {
			description := ""
			if row.description != nil {
				description = *row.description
			}

			fruit = &FruitDto{ID: row.fruitID, Name: row.fruitName, Description: description}
			byID[row.fruitID] = fruit
			order = append(order, row.fruitID)
		}

		// LEFT JOIN: a fruit with no prices yields one row with every p_/s_ column null.
		if row.price != nil && row.storeID != nil {
			fruit.StorePrices = append(fruit.StorePrices, StoreFruitPriceDto{
				Store: StoreDto{
					ID:       *row.storeID,
					Name:     *row.storeName,
					Currency: *row.currency,
					Address:  AddressDto{Address: *row.address, City: *row.city, Country: *row.country},
				},
				Price: *row.price,
			})
		}
	}

	fruits := make([]FruitDto, 0, len(order))
	for _, id := range order {
		fruits = append(fruits, *byID[id])
	}

	return fruits
}

type pgxFruitRepository struct {
	pool *pgxpool.Pool
}

func newPgxFruitRepository(pool *pgxpool.Pool) *pgxFruitRepository {
	return &pgxFruitRepository{pool: pool}
}

func (r *pgxFruitRepository) scanRows(rows pgxScanner) ([]fruitRow, error) {
	var result []fruitRow

	for rows.Next() {
		var row fruitRow

		if err := rows.Scan(
			&row.fruitID, &row.fruitName, &row.description, &row.price,
			&row.storeID, &row.storeName, &row.currency, &row.address, &row.city, &row.country,
		); err != nil {
			return nil, err
		}

		result = append(result, row)
	}

	return result, rows.Err()
}

// Panache listAll().
func (r *pgxFruitRepository) ListAll(ctx context.Context) ([]FruitDto, error) {
	rows, err := r.pool.Query(ctx, fruitRowsSelect)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	parsed, err := r.scanRows(rows)
	if err != nil {
		return nil, err
	}

	return groupFruitRows(parsed), nil
}

// Panache find("name", name).firstResultOptional().
func (r *pgxFruitRepository) FindByName(ctx context.Context, name string) (*FruitDto, error) {
	rows, err := r.pool.Query(ctx, fruitRowsSelect+" WHERE f.name = $1", name)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	parsed, err := r.scanRows(rows)
	if err != nil {
		return nil, err
	}

	fruits := groupFruitRows(parsed)
	if len(fruits) == 0 {
		return nil, nil
	}

	return &fruits[0], nil
}

// Panache persist(). fruits.id has no DEFAULT in scripts/dbdata/db.sql, so the id is drawn from
// the fruits_seq sequence in the same statement as the insert - one round trip, matching
// Hibernate's GenerationType.SEQUENCE with allocationSize = 1 in effect (one nextval per row)
// without its two-statement mechanics. Same approach as the Rust module's FruitRepository::persist.
//
// Deliberately maps only Name and Description, matching FruitMapper.map(FruitDTO -> Fruit)'s
// comment: "the rest of the relationships aren't built out yet".
func (r *pgxFruitRepository) Persist(ctx context.Context, req CreateFruitRequest) (FruitDto, error) {
	var id int64

	err := r.pool.QueryRow(
		ctx,
		"INSERT INTO fruits (id, name, description) VALUES (nextval('fruits_seq'), $1, $2) RETURNING id",
		req.Name, req.Description,
	).Scan(&id)
	if err != nil {
		return FruitDto{}, err
	}

	description := ""
	if req.Description != nil {
		description = *req.Description
	}

	return FruitDto{ID: id, Name: req.Name, Description: description}, nil
}

// pgx.Rows and gorm-free code both need only Next/Scan/Err - a tiny interface keeps scanRows
// independent of pgx's concrete Rows type, useful for the unit tests in repository_pgx_test.go.
type pgxScanner interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}
