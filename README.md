## 🐚 WoRMS Cache API

![Image](https://www.marinespecies.org/images/layout/WoRMS_logo_neg_blue.png)

![Image](https://www.researchgate.net/publication/321685430/figure/fig2/AS%3A569358889623553%401512757145165/Schematic-representation-of-Linnaeuss-classification-of-marine-animals-at-class-and.png)

![Image](https://rachelbrooksart.com/cdn/shop/files/MarineLifetheOpenOceanPrint-RachelBrooks.jpg?v=1749397649)

![Image](https://i.etsystatic.com/10484006/r/il/ad8d17/990508078/il_fullxfull.990508078_exz2.jpg)

A high-performance local cache and search API for **WoRMS (World Register of Marine Species)** taxonomic data.

Built to eliminate latency, external dependency risk, and redundant API calls to the official WoRMS REST service:

👉 [https://www.marinespecies.org/rest/](https://www.marinespecies.org/rest/)

---

# 1. Overview

This repository implements a **local WoRMS cache database and REST API**, designed to:

* Cache WoRMS taxonomic records locally
* Store full classification hierarchy (root → leaf)
* Store synonyms and vernacular names
* Provide fast scientific and fuzzy name matching
* Support autocomplete and annotation workflows
* Fall back to live WoRMS only when required

---

# 2. Problem Statement

Direct calls to the WoRMS REST API introduce:

* ❌ Latency in annotation workflows
* ❌ Dependency on external service uptime
* ❌ Repeated identical taxon requests

### Solution

✔ Local PostgreSQL-backed cache
✔ Daily refresh job
✔ Full lineage storage
✔ Trigram + Taxamatch fuzzy matching
✔ REST API compatible with WoRMS-style responses

---

# 3. Architecture

## System Components

```
PostgreSQL (Cache DB)
        ↑
Django REST API
        ↑
Taxamatch Service (Ruby microservice)
        ↑
WoRMS REST API (fallback + ingestion)
```

### Services

| Service     | Purpose                                   |
| ----------- | ----------------------------------------- |
| `db`        | PostgreSQL 16                             |
| `api`       | Django REST API                           |
| `taxamatch` | Fuzzy name matching (Tony Rees algorithm) |

---

# 4. Data Model

The local cache stores:

## Taxa (`taxa`)

| Field             | Description              |
| ----------------- | ------------------------ |
| `aphia_id`        | Primary key              |
| `scientific_name` | Canonical name           |
| `rank`            | Taxonomic rank           |
| `status`          | accepted / unaccepted    |
| `valid_taxon_id`  | Points to accepted taxon |
| `parent_id`       | Parent taxon (hierarchy) |
| `worms_modified`  | Timestamp from WoRMS     |
| `cached_at`       | Cache timestamp          |

---

## Ranks (`ranks`)

Stores WoRMS rank definitions (`taxonRankID`, `taxonRank`).

---

## Vernaculars (`vernaculars`)

| Field           | Description |
| --------------- | ----------- |
| `taxon_id`      | FK to taxa  |
| `name`          | Common name |
| `language_code` | ISO 639-3   |

---

## NameIndex (`name_index`)

Optimized scientific name search index using:

* Normalized canonical name
* Genus / epithet extraction
* Prefix indexes
* PostgreSQL trigram GIN indexes

Used for:

* Autocomplete
* Candidate selection for Taxamatch
* High-performance fuzzy search

---

# 5. Cache Ingestion

## Initial Ingestion

Run:

```bash
docker compose -f docker/docker-compose.yml run --rm api \
  python manage.py ingest_worms --file initial_aphia_ids.txt --add-ranks
```

### What Happens

For each AphiaID:

1. Fetch `/AphiaRecordByAphiaID/{id}`
2. If unaccepted → also fetch valid AphiaID
3. Fetch `/AphiaClassificationByAphiaID/{id}`
4. Walk full parent lineage
5. Store:

   * Taxon
   * Valid taxon
   * Parent chain
   * Vernacular names
   * Synonyms
6. Update timestamps
7. Maintain referential integrity

All wrapped in atomic transactions.

---

## Rank Ingestion

Option `--add-ranks` fetches and stores WoRMS rank definitions.

---

# 6. Name Index Rebuild

After ingestion:

```bash
docker compose -f docker/docker-compose.yml run --rm api \
  python manage.py rebuild_name_index
```

This:

* Parses genus/epithet
* Normalizes canonical names
* Adds synonyms as separate index rows
* Bulk inserts with chunking

---

# 7. API Endpoints

Base URL:

```
http://localhost:8000/
```

---

## Taxa

### List

```
GET /taxa/
```

Query params:

* `scientific_name`
* `rank`

---

### Retrieve

```
GET /taxa/{aphia_id}/
```

Resolves synonyms automatically.

---

### Classification (WoRMS-style)

```
GET /taxa/classification/{aphia_id}/
```

Returns nested structure:

```json
{
  "AphiaID": 1,
  "rank": "Kingdom",
  "scientificname": "Animalia",
  "child": {
    ...
  }
}
```

---

### Synonyms

```
GET /taxa/synonyms/{aphia_id}/
```

---

## AJAX Autocomplete

```
GET /taxa/ajax_by_name_part/{NamePart}/
```

Supports:

* rank filtering
* vernacular matching
* trigram similarity
* exclusion lists
* max_matches

---

## Batch Scientific Name Matching

```
GET /taxa/match_names?scientificnames[]=Asterias rubens
```

Uses:

1. Candidate narrowing via NameIndex
2. Fuzzy matching via Taxamatch microservice
3. Deduplicated valid taxa resolution

Limit: 50 names per request

---

## Pair Matching

```
GET /taxa/match_names_pair?scientificname1=Asterias rubens&scientificname2=Asterias rubens
```

Returns:

```json
{ "match": true }
```

---

## Vernaculars

```
GET /vernaculars/{aphia_id}/
```

Optional:

* `language_code`
* `follow_valid=true`

---

## Ranks

```
GET /ranks/
```

---

## Name Index

```
GET /name_index/
```

---

# 8. Fallback Behavior

If a taxon is:

* ❌ Not in cache
* ❌ Missing classification
* ❌ Missing valid taxon

The system may:

1. Call live WoRMS
2. Optionally insert result into cache

(Controlled via service layer `worms_client` + `cache_policy`)

---

# 9. Scheduled Refresh

Daily refresh is handled by:

```
refresh_worms.py
```

Recommended setup:

* Kubernetes CronJob
* Docker scheduled task
* Or host-level cron

Example:

```bash
0 3 * * * docker compose run --rm api python manage.py refresh_worms
```

Refresh updates:

* Modified records
* New taxa referenced in annotations
* Rank updates if required

---

# 10. Docker Setup

## Start services

```bash
cd docker
docker compose up --build
```

Services:

* API → [http://localhost:8000](http://localhost:8000)
* Taxamatch → [http://localhost:8082](http://localhost:8082)
* PostgreSQL → localhost:5435

---

# 11. PostgreSQL Optimizations

Enabled:

* `pg_trgm` extension
* GIN trigram indexes
* Prefix indexes
* Compound rank/status indexes
* FK integrity

Designed for high-volume annotation systems.

---

# 12. Acceptance Criteria Coverage

✔ Local WoRMS cache exists
✔ Queryable by scientific name
✔ Stores full AphiaID record
✔ Stores full parent lineage
✔ Stores valid taxon resolution
✔ Daily refresh mechanism
✔ API does not depend on live WoRMS
✔ Fallback supported
✔ Documentation provided

---

# 13. Development

### Run tests

```bash
pytest
```

### Lint

```bash
ruff check .
```

### Coverage

See:

```
coverage_reports/coverage.xml
```

---

# 14. Future Improvements

* Incremental sync based on `worms_modified`
* Cache eviction strategy
* Background async ingestion
* Metrics and monitoring
* OpenAPI publishing
* Distributed caching (Redis layer)

---

# 15. Summary

This project provides:

* ⚡ Fast local taxonomic resolution
* 🔎 Advanced fuzzy scientific name matching
* 🌍 Full WoRMS-compatible hierarchy
* 🧠 Synonym + vernacular awareness
* 🛡 External dependency isolation

It is optimized for **annotation systems**, **biodiversity databases**, and **marine taxonomy workflows** requiring high availability and speed.
