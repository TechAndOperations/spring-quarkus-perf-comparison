package main

// Mirrors org.acme.dto.AddressDTO. Field order matches the Java record's declaration order, same
// convention used by the Node.js and Rust modules - both differ harmlessly from
// quarkus3-virtual's alphabetical order (its Jackson reflection-free serializers sort keys; see
// nodejs/README.md, "JSON key order differs ... harmlessly"). encoding/json marshals struct
// fields in declaration order, same as serde in the Rust module.
type AddressDto struct {
	Address string `json:"address"`
	City    string `json:"city"`
	Country string `json:"country"`
}

// Mirrors org.acme.dto.StoreDTO.
type StoreDto struct {
	ID       int64      `json:"id"`
	Name     string     `json:"name"`
	Currency string     `json:"currency"`
	Address  AddressDto `json:"address"`
}

// Mirrors org.acme.dto.StoreFruitPriceDTO. Price is never omitted even when zero - it is not
// "empty" for Jackson's NON_EMPTY inclusion, only null/blank/empty-collection values are.
type StoreFruitPriceDto struct {
	Store StoreDto `json:"store"`
	Price float64  `json:"price"`
}

// Mirrors org.acme.dto.FruitDTO.
//
// Description and StorePrices use `omitempty` to replicate
// quarkus.jackson.serialization-inclusion: non-empty from
// quarkus3-virtual/src/main/resources/application.yml - the same rule the Node.js and Rust
// modules implement explicitly in their mapping code. Go's `omitempty` treats an empty string and
// a nil/zero-length slice as empty, which is exactly the behaviour needed here, so no manual
// checks are required the way they are in the other two modules.
type FruitDto struct {
	ID          int64                 `json:"id"`
	Name        string                `json:"name"`
	Description string                `json:"description,omitempty"`
	StorePrices []StoreFruitPriceDto  `json:"storePrices,omitempty"`
}

// Request body for POST /fruits. Mirrors FruitMapper.map(FruitDTO -> Fruit)'s deliberate
// behaviour: only Name and Description are read - id/storePrices sent by a client are ignored,
// same as the Node.js and Rust modules.
//
// Description is a *string (not a plain string) specifically so that an absent field and a
// present-but-empty field are distinguishable: nil means "no description was sent" (persisted as
// SQL NULL, matching Java's Fruit.setDescription(fruitDTO.description()) when the DTO's
// description is null), while a pointer to "" means an explicit empty string was sent. The Rust
// module cannot make this distinction (its DTO field is a non-Option String, so a missing field
// is rejected by serde before validation ever runs - see rust/README.md); this is a case where
// Go achieves closer parity with Java's null-handling than Rust does.
type CreateFruitRequest struct {
	Name        string  `json:"name"`
	Description *string `json:"description,omitempty"`
}
