## Taxamatch service

This is a small Ruby/Sinatra microservice (`taxamatch_service/`) that provides fast fuzzy matching between user-supplied scientific names and a set of candidate names produced by the Django API (`NameIndex`). It implements Tony Rees’ **TaxaMatch** algorithm via the `taxamatch_rb` gem, and is used by the Django endpoints `GET /taxa/match_names` and `GET /taxa/match_names_pair` to decide which candidate `NameIndex` rows truly match the query.

### What it does

The service exposes two endpoints:

* `GET /health` → returns `{ ok: true, version: ... }` for monitoring.
* `POST /match` → accepts a JSON body with a `queries` array, where each query includes:

  * `input`: the query name string
  * `candidates`: an array of `{ id, name }` objects (typically NameIndex row id + raw name)

It returns one result per query including:

* `matched_ids`: the subset of candidate `id`s that match the input according to TaxaMatch
* `mode`: either `single_token` or `full_taxamatch`
* `errors`: any parsing/matching warnings (e.g., candidate truncation)

### Matching modes

To keep matching fast and robust, the service chooses an algorithm based on the number of tokens in the input:

* **`single_token` mode** (1-token input, e.g. `"Asterias"`):
  Performs genus/species-oriented matching against each candidate by:

  * comparing the input against candidate genus (`match_genera`)
  * also comparing the input against a “species token” (candidate species if present, otherwise genus) via `match_species`
    A candidate is considered a match if **either genus or species comparison matches**.

* **`full_taxamatch` mode** (2+ tokens, e.g. `"Asterias rubens"`):
  Uses the TaxaMatch atomizer to parse both input and candidate. If parsing succeeds it runs `taxamatch_preparsed`; otherwise it falls back to `taxamatch(input, candidate)`.

### Safety limits & configuration

To protect the service from overly large requests, the API enforces:

* `MAX_NAMES` (default **50**) → maximum number of query items per request
* `MAX_CANDIDATES_PER_NAME` (default **300**) → candidates are truncated above this limit and an error note is added

These are configurable via environment variables (see `docker-compose.yml`).

### Role in the overall pipeline

1. Django builds a **candidate set** from the local cache (`NameIndex`, trigram + indexes).
2. Django sends `(input, candidates)` batches to Taxamatch.
3. Taxamatch returns `matched_ids`.
4. Django maps those matched ids back to **AphiaIDs / Taxon records**, resolves synonyms to valid taxa, and returns WoRMS-like responses.

This design keeps the expensive fuzzy matching logic out of the main API process, while still enabling matching for autocomplete and batch name reconciliation.

## Development Workflow

To run the tests for the ruby microservice:

```bash
docker compose -f docker/docker-compose.yml run --rm -e RACK_ENV=test taxamatch bundle _2.4.22_ exec rspec
```

## Endoint example

Request:

```bash
curl -X POST http://localhost:8080/match \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      {
        "input": "Asterias rubens",
        "candidates": [
          { "id": 1, "name": "Asterias rubens" },
          { "id": 2, "name": "Asterias forbesi" },
          { "id": 3, "name": "Pisaster ochraceus" }
        ]
      }
    ]
  }'
```

Response:

```json
{
  "results": [
    {
      "input": "Asterias rubens",
      "matched_ids": [1],
      "mode": "full_taxamatch",
      "errors": []
    }
  ]
}
```
