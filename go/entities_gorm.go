package main

// GORM entities, used only in QUERY_MODE=orm. Mirror the JPA entities in
// quarkus3-virtual/src/main/java/org/acme/domain/ and the TypeORM entities in
// nodejs/src/domain/ - this is the Go analogue of the "idiomatic ORM path" question already
// explored for those two modules.

// Mirrors org.acme.domain.Address (an @Embeddable record). GORM's `embedded` tag flattens these
// columns onto the owning table with no prefix, matching the bare `address`/`city`/`country`
// columns in scripts/dbdata/db.sql - the same requirement documented for the TypeORM module's
// `{ prefix: false }` (nodejs/src/domain/store.entity.ts).
type GormAddress struct {
	Address string
	City    string
	Country string
}

// Mirrors org.acme.domain.Store (@Entity, @Cacheable). id has no DEFAULT in
// scripts/dbdata/db.sql (Hibernate's GenerationType.SEQUENCE draws it from stores_seq), so GORM
// must never be allowed to auto-assign it - see gormFruitRepository.Persist.
type GormStore struct {
	ID       int64 `gorm:"primaryKey;autoIncrement:false"`
	Name     string
	Currency string
	Address  GormAddress `gorm:"embedded"`
}

func (GormStore) TableName() string { return "stores" }

// Mirrors org.acme.domain.Fruit (@Entity). StorePrices is the inverse side of the relationship,
// matching @OneToMany(mappedBy = "fruit") - not a column, populated only via Preload.
type GormFruit struct {
	ID          int64  `gorm:"primaryKey;autoIncrement:false"`
	Name        string
	Description string
	StorePrices []GormStoreFruitPrice `gorm:"foreignKey:FruitID"`
}

func (GormFruit) TableName() string { return "fruits" }

// Mirrors org.acme.domain.StoreFruitPrice. The Java entity uses an @EmbeddedId
// (StoreFruitPriceId) with @MapsId; GORM has no embedded-id equivalent, so the composite key is
// expressed as two primaryKey-tagged columns - the same pattern used by the Rust module's
// StoreFruitPrice entity (rust/src/repository.rs) and the TypeORM module
// (nodejs/src/domain/store-fruit-price.entity.ts).
type GormStoreFruitPrice struct {
	FruitID int64     `gorm:"column:fruit_id;primaryKey"`
	StoreID int64     `gorm:"column:store_id;primaryKey"`
	Store   GormStore `gorm:"foreignKey:StoreID"`
	Price   float64
}

func (GormStoreFruitPrice) TableName() string { return "store_fruit_prices" }
