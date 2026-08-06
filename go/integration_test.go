package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

// Mirrors quarkus3-virtual's FruitControllerEndToEndTest and the Node.js/Rust modules'
// equivalents (nodejs/test/fruit.e2e-spec.ts, rust/tests/fruit_test.rs): hits the real
// endpoints against the real database, seeded by scripts/dbdata/db.sql.
//
// Requires the shared Postgres container to be up (cd scripts && ./infra.sh -s). OpenTelemetry is
// disabled here so the suite does not need the LGTM collector.
//
// Every test in this file runs against BOTH query modes (see newTestServer) - unlike the Node.js
// and Rust modules, where the pgx-equivalent "which query mode is faster" comparison was only
// checked by hand after the fact with a manual curl diff. Running both modes through the same
// assertions on every `go test` invocation catches an ORM/raw-SQL divergence immediately instead
// of relying on someone remembering to re-check it later.
func newTestServer(t *testing.T, queryMode string) string {
	t.Helper()

	os.Setenv("OTEL_SDK_DISABLED", "true")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	repository, closeDB, err := connect(ctx, queryMode)
	if err != nil {
		t.Skipf("database not reachable (query mode=%s): %v", queryMode, err)
	}
	t.Cleanup(closeDB)

	server := httptest.NewServer(newMux(newFruitService(repository)))
	t.Cleanup(server.Close)

	return server.URL
}

func decodeJSON[T any](t *testing.T, resp *http.Response) T {
	t.Helper()
	defer resp.Body.Close()

	var v T
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	return v
}

func forEachQueryMode(t *testing.T, run func(t *testing.T, baseURL string)) {
	for _, mode := range []string{"sql", "orm"} {
		t.Run(mode, func(t *testing.T) {
			run(t, newTestServer(t, mode))
		})
	}
}

func TestGetFruitsReturnsSeededFruitsWithNestedStorePrices(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		resp, err := http.Get(baseURL + "/fruits")
		if err != nil {
			t.Fatal(err)
		}

		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}

		fruits := decodeJSON[[]FruitDto](t, resp)
		if len(fruits) < 10 {
			t.Fatalf("expected >= 10 seeded fruits, got %d", len(fruits))
		}

		var apple *FruitDto
		for i := range fruits {
			if fruits[i].Name == "Apple" {
				apple = &fruits[i]
			}
		}

		if apple == nil {
			t.Fatal("Apple should be seeded")
		}

		if apple.ID != 1 || apple.Description != "Hearty fruit" {
			t.Fatalf("unexpected Apple: %+v", apple)
		}

		var store1Price *StoreFruitPriceDto
		for i := range apple.StorePrices {
			if apple.StorePrices[i].Store.Name == "Store 1" {
				store1Price = &apple.StorePrices[i]
			}
		}

		if store1Price == nil {
			t.Fatal("Store 1 price should be seeded for Apple")
		}

		if store1Price.Price != 1.29 {
			t.Fatalf("expected price 1.29, got %v", store1Price.Price)
		}

		if store1Price.Store.Currency != "USD" || store1Price.Store.Address.City != "Anytown" {
			t.Fatalf("unexpected store: %+v", store1Price.Store)
		}
	})
}

func TestGetFruitByNameReturnsTheFruit(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		resp, err := http.Get(baseURL + "/fruits/Apple")
		if err != nil {
			t.Fatal(err)
		}

		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}

		fruit := decodeJSON[FruitDto](t, resp)
		if fruit.Name != "Apple" || fruit.Description != "Hearty fruit" {
			t.Fatalf("unexpected fruit: %+v", fruit)
		}
	})
}

func TestGetFruitByNameReturns404WithEmptyBodyWhenNotFound(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		resp, err := http.Get(baseURL + "/fruits/NotAFruit")
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusNotFound {
			t.Fatalf("expected 404, got %d", resp.StatusCode)
		}

		// A NestJS/JAX-RS-style JSON error body ({"statusCode":404,...}) would fail this check.
		body, _ := io.ReadAll(resp.Body)
		if len(body) != 0 {
			t.Fatalf("expected an empty body, got %q", body)
		}
	})
}

func TestPostFruitsCreatesAFruitAndReturns200(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		name := t.Name() + "-" + time.Now().Format("150405.000000000")

		reqBody, _ := json.Marshal(map[string]string{"name": name, "description": "Summer fruit"})

		resp, err := http.Post(baseURL+"/fruits", "application/json", bytes.NewReader(reqBody))
		if err != nil {
			t.Fatal(err)
		}

		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}

		fruit := decodeJSON[FruitDto](t, resp)
		if fruit.Name != name || fruit.Description != "Summer fruit" {
			t.Fatalf("unexpected fruit: %+v", fruit)
		}

		if fruit.ID <= 10 {
			t.Fatalf("expected a sequence-generated id > 10, got %d", fruit.ID)
		}

		// storePrices is unset on create (see FruitMapper-equivalent behaviour in
		// repository_pgx.go / repository_gorm.go) and omitted when empty.
		body, _ := json.Marshal(fruit)
		if strings.Contains(string(body), "storePrices") {
			t.Fatalf("expected storePrices to be omitted, got %s", body)
		}
	})
}

func TestPostFruitsRejectsABlankName(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		// An empty string, not an absent field. Go's zero value for string ("") makes an absent
		// "name" key and an explicit empty string behave identically here - unlike the Rust
		// module, where a missing field is rejected by serde with 422 before validation ever runs
		// (see rust/README.md); this module has no such asymmetry.
		reqBody, _ := json.Marshal(map[string]string{"name": "", "description": "No name"})

		resp, err := http.Post(baseURL+"/fruits", "application/json", bytes.NewReader(reqBody))
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("expected 400, got %d", resp.StatusCode)
		}
	})
}

func TestPostFruitsRejectsAMissingNameField(t *testing.T) {
	forEachQueryMode(t, func(t *testing.T, baseURL string) {
		reqBody, _ := json.Marshal(map[string]string{"description": "No name"})

		resp, err := http.Post(baseURL+"/fruits", "application/json", bytes.NewReader(reqBody))
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		// Same 400 as the blank-string case above - see the comment in
		// TestPostFruitsRejectsABlankName for why Go does not have the Rust module's 422/400 split.
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("expected 400, got %d", resp.StatusCode)
		}
	})
}
