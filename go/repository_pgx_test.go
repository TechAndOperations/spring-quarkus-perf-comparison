package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func ptr[T any](v T) *T { return &v }

func TestGroupFruitRowsMergesMultiplePricesForOneFruit(t *testing.T) {
	rows := []fruitRow{
		{fruitID: 1, fruitName: "Apple", description: ptr("Hearty fruit"),
			price: ptr(1.29), storeID: ptr(int64(1)), storeName: ptr("Store 1"), currency: ptr("USD"),
			address: ptr("123 Main St"), city: ptr("Anytown"), country: ptr("USA")},
		{fruitID: 1, fruitName: "Apple", description: ptr("Hearty fruit"),
			price: ptr(2.49), storeID: ptr(int64(2)), storeName: ptr("Store 2"), currency: ptr("EUR"),
			address: ptr("456 Main St"), city: ptr("Paris"), country: ptr("France")},
	}

	fruits := groupFruitRows(rows)

	if len(fruits) != 1 {
		t.Fatalf("expected 1 fruit, got %d", len(fruits))
	}

	if len(fruits[0].StorePrices) != 2 {
		t.Fatalf("expected 2 store prices, got %d", len(fruits[0].StorePrices))
	}
}

func TestGroupFruitRowsOmitsEmptyFieldsLikeJacksonNonEmpty(t *testing.T) {
	// A LEFT JOIN with no matching price yields one row with every p_/s_ column null.
	rows := []fruitRow{{fruitID: 11, fruitName: "Grapefruit"}}

	fruits := groupFruitRows(rows)
	body, err := json.Marshal(fruits[0])
	if err != nil {
		t.Fatal(err)
	}

	want := `{"id":11,"name":"Grapefruit"}`
	if string(body) != want {
		t.Fatalf("got %s, want %s", body, want)
	}
}

func TestGroupFruitRowsPreservesFirstAppearanceOrder(t *testing.T) {
	// Go maps, like Rust's HashMap and unlike JavaScript's Map, do not iterate in insertion
	// order - this test guards the explicit order-tracking slice in groupFruitRows.
	rows := []fruitRow{
		{fruitID: 1, fruitName: "Apple"},
		{fruitID: 2, fruitName: "Pear"},
		{fruitID: 1, fruitName: "Apple", price: ptr(0.99), storeID: ptr(int64(1)), storeName: ptr("Store 1"),
			currency: ptr("USD"), address: ptr("x"), city: ptr("y"), country: ptr("z")},
	}

	fruits := groupFruitRows(rows)

	if len(fruits) != 2 || fruits[0].Name != "Apple" || fruits[1].Name != "Pear" {
		t.Fatalf("unexpected order: %+v", fruits)
	}

	if len(fruits[0].StorePrices) != 1 {
		t.Fatalf("expected the third row's price to merge into the first Apple entry")
	}
}

func TestFruitDtoJSONKeyOrderMatchesDeclarationOrder(t *testing.T) {
	// encoding/json marshals in struct declaration order, matching the Java DTO's record field
	// order - the same convention the Node.js and Rust modules use, and a harmless divergence
	// from quarkus3-virtual's alphabetically-sorted reflection-free serializers (see
	// nodejs/README.md, "JSON key order differs ... harmlessly").
	fruit := FruitDto{
		ID: 1, Name: "Apple", Description: "Hearty fruit",
		StorePrices: []StoreFruitPriceDto{{
			Store: StoreDto{ID: 1, Name: "Store 1", Currency: "USD",
				Address: AddressDto{Address: "123 Main St", City: "Anytown", Country: "USA"}},
			Price: 1.29,
		}},
	}

	body, err := json.Marshal(fruit)
	if err != nil {
		t.Fatal(err)
	}

	want := `{"id":1,"name":"Apple","description":"Hearty fruit","storePrices":[{"store":{"id":1,"name":"Store 1","currency":"USD","address":{"address":"123 Main St","city":"Anytown","country":"USA"}},"price":1.29}]}`
	if string(body) != want {
		t.Fatalf("got  %s\nwant %s", body, want)
	}
}

func TestFruitDtoJSONNumbersNotStrings(t *testing.T) {
	// pgx returns Postgres numeric/bigint as Go's native int64/float64 (unlike node-postgres,
	// which returns them as strings - see nodejs/src/domain/numeric.transformer.ts), so there
	// is no coercion step needed here. This test guards against a future change accidentally
	// introducing string-typed id/price fields.
	body, err := json.Marshal(FruitDto{ID: 1, Name: "Apple", StorePrices: []StoreFruitPriceDto{{Price: 1.29}}})
	if err != nil {
		t.Fatal(err)
	}

	for _, want := range []string{`"id":1,`, `"price":1.29`} {
		if !strings.Contains(string(body), want) {
			t.Fatalf("expected %s in %s", want, body)
		}
	}
}
