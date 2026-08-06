package main

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
)

// Mirrors org.acme.rest.FruitController. Contract is the repo-wide openapi.yml.
//
// Unlike the NestJS module (nodejs/src/rest/fruit.controller.ts), no explicit override is
// needed for either JAX-RS-matching behaviour: net/http's default response status is 200 for any
// handler that never calls WriteHeader before writing a body, for any method including POST
// (NestJS defaults POST to 201); and writing WriteHeader(404) with no body already produces an
// empty 404 (no JSON error object) - same as the Rust module, and unlike NestJS which needs
// @Res() to bypass its default JSON-error 404.
func newMux(service *FruitService) *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /fruits", func(w http.ResponseWriter, r *http.Request) {
		fruits, err := service.GetAllFruits(r.Context())
		if err != nil {
			writeInternalError(w, err)
			return
		}

		writeJSON(w, fruits)
	})

	mux.HandleFunc("GET /fruits/{name}", func(w http.ResponseWriter, r *http.Request) {
		fruit, err := service.GetFruitByName(r.Context(), r.PathValue("name"))
		if err != nil {
			writeInternalError(w, err)
			return
		}

		if fruit == nil {
			w.WriteHeader(http.StatusNotFound)
			return
		}

		writeJSON(w, fruit)
	})

	mux.HandleFunc("POST /fruits", func(w http.ResponseWriter, r *http.Request) {
		var req CreateFruitRequest

		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}

		// Mirrors class-validator's @IsNotEmpty on FruitDTO.name in the Node.js module and
		// Hibernate Validator's @NotBlank in the Java module. Go's zero value for string ("")
		// covers both an absent "name" key and an explicit empty string identically - unlike the
		// Rust module, where a missing field is rejected by serde as a 422 before this check ever
		// runs (see rust/README.md); Go does not have that asymmetry.
		if strings.TrimSpace(req.Name) == "" {
			http.Error(w, "Name is mandatory", http.StatusBadRequest)
			return
		}

		fruit, err := service.CreateFruit(r.Context(), req)
		if err != nil {
			writeInternalError(w, err)
			return
		}

		writeJSON(w, fruit)
	})

	mux.HandleFunc("GET /q/health", health)
	mux.HandleFunc("GET /q/health/live", health)
	mux.HandleFunc("GET /q/health/ready", health)

	return mux
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")

	if err := json.NewEncoder(w).Encode(v); err != nil {
		slog.Error("failed to encode response", "error", err)
	}
}

// Maps any repository failure to a 500. The load test never exercises the write path and the read
// paths only fail on infrastructure problems (pool exhaustion, DB unreachable), so this stays a
// single catch-all rather than a per-error-kind mapping - same scope as the Rust module's ApiError.
func writeInternalError(w http.ResponseWriter, err error) {
	slog.Error("request failed", "error", err)
	w.WriteHeader(http.StatusInternalServerError)
}

// Minimal stand-in for the quarkus-smallrye-health endpoints the other modules expose at
// /q/health. Nothing in the benchmark pipeline calls these (time-to-first-request polls
// TARGET_URL instead); they exist for parity when poking at a running app by hand.
func health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"status": "UP", "checks": []any{}})
}
