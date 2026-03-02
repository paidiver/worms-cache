# WoRMS Cache API

A local cache and search API for **WoRMS (World Register of Marine Species)** taxonomic data.

Built to eliminate latency, external dependency risk, and redundant API calls to the official WoRMS REST service: [https://www.marinespecies.org/rest/](https://www.marinespecies.org/rest/)


## Overview

This repository implements a local WoRMS cache database and REST API, designed to:

* Cache WoRMS taxonomic records locally
* Store full classification hierarchy (root → leaf)
* Store synonyms and vernacular names
* Store all ranks and their relationships
* Provide fast scientific and fuzzy name matching
* Support autocomplete and annotation workflows

## Requirements

* Docker
* Docker Compose

## Architecture

### Project Structure

```text
.
├── api/                # Django app (API)
├── config/             # Django project configuration
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── scripts/
├── taxamatch_service/  # Ruby microservice for fuzzy name matching
├── manage.py
├── pyproject.toml      # Project metadata & dependencies (Poetry)
├── poetry.lock         # Locked dependency versions
├── tox.ini             # Test, lint, and format automation
├── ruff.toml           # Ruff configuration
├── README.md
├── LICENSE
└── .env.example
```

### Services

| Service     | Purpose                                   |
| ----------- | ----------------------------------------- |
| `db`        | PostgreSQL 16                             |
| `api`       | Django REST API                           |
| `taxamatch` | Fuzzy name matching (Tony Rees algorithm) |

### Data Model

The local cache stores:

* **Taxa (`taxa`)**: Full AphiaID records with hierarchy and valid taxon resolution. Fields: `aphia_id`, `scientific_name`, `rank`, `status`, `valid_taxon_id`, `parent_id`, `worms_modified`, `cached_at`.
* **Ranks (`ranks`)**: WoRMS rank definitions (`taxonRankID`, `taxonRank`).
* **Vernaculars (`vernaculars`)**: Common names with language codes. Fields: `taxon_id` (FK to taxa), `name`, `language_code`.
* **NameIndex (`name_index`)**: Optimized search index for scientific names, including synonyms. Fields: `id`, `taxon_id` (FK to taxa), `canonical_name`, `genus`, `epithet`, `is_synonym`.

The `NameIndex` is a denormalized table designed for fast lookup and fuzzy matching, with trigram indexes on `canonical_name` and prefix indexes on `genus` and `epithet`. It includes both accepted names and synonyms as separate rows. It is used for autocomplete, candidate selection for Taxamatch, and high-performance fuzzy search.

### Taxamatch Service

A separate Ruby microservice implements the Tony Rees Taxamatch algorithm for fuzzy name matching. The Django API calls this service to get candidate matches for user-provided names, which are then resolved to AphiaIDs using the local cache. More information on the Taxamatch service can be found in the [Taxamatch Documentation](docs/TAXAMATCH.md) document.

## Quick Start

### 1. Create environment file

Configuration is provided via environment variables defined in `.env`.

Start from the example file:

```bash
cp .env.example .env
```

Example contents:

```env
POSTGRES_DB=annotationsdb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_HOST=db
POSTGRES_PORT=5432

DJANGO_SECRET_KEY=dev-secret-key-change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
WORMS_API_BASE_URL=https://marinespecies.org/rest
CACHED_WORMS_API_BASE_URL=https://marinespecies.org/rest
TAXAMATCH_URL=http://taxamatch:8080
```

### 2. Build and run the stack

```bash
docker compose -f docker/docker-compose.yml up --build
```

This will:

* Start PostgreSQL/PostGIS
* Run Django migrations
* Start the Django development server
* Start the Taxamatch microservice

### 3. Test the API

Health endpoint:

```
http://localhost:8000/api/health/
```

Expected response:

```json
{"status": "ok"}
```

API schema and documentation:

```
http://localhost:8000/api/docs/
```


## Database Migrations

Create new migrations after modifying models:

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py makemigrations
```

To add some descriptive name to migration file that is going to generate, use `--name` flag while running migration command. And once the migration file is created, make sure to add some descriptive docstring on top of the file as well.

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py makemigrations --name migration_description
```

Apply migrations:

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py migrate
```

## Cache Ingestion

### Initial Ingestion

To run the innitial ingestion of WoRMS data, you can use the `ingest_worms` management command. This command takes a file containing a list of AphiaIDs to ingest, one per line. An example of the input file (`initial_aphia_ids.txt`) is included in the repository, containing a small set of AphiaIDs for testing.

```bash
docker compose -f docker/docker-compose.yml run --rm api \
  python manage.py ingest_worms --file initial_aphia_ids.txt --add-ranks
```

The flag `--file` specifies the path to the input file containing AphiaIDs. The `--add-ranks` flag indicates that WoRMS rank definitions should also be fetched and stored during ingestion.

For each AphiaID described in the input file, the ingestion process will:

1. Fetch `/AphiaRecordByAphiaID/{id}` for the taxon record
2. If the status of the record is unaccepted, it will also fetch valid AphiaID
3. Fetch `/AphiaClassificationByAphiaID/{id}` for the full parent lineage
4. Walk full parent lineage
5. Store:

   * Taxon
   * Valid taxon
   * Parent chain
   * Vernacular names
   * Synonyms
6. Update timestamps
7. Maintain referential integrity
8. Fetch `/AphiaVernacularsByAphiaID/{id}` for vernacular names and store them in the `Vernacular` table, linked to the corresponding `Taxon` via a foreign key.
9. Fetch `/AphiaSynonymsByAphiaID/{id}` for synonyms and store them in the Taxon table as separate rows, linked to the accepted taxon via the `valid_taxon_id` field.
10. Option `--add-ranks` fetches and stores WoRMS rank definitions from the `/AphiaTaxonRanksByID/{id}` endpoint in the `Rank` table.

All wrapped in atomic transactions.

### Name Index Rebuild

After ingestion, in the same command, it will:
* Parses genus/epithet of each taxon added to the database
* Normalizes canonical names
* Adds synonyms as separate index rows
* Bulk inserts with chunking data into the `NameIndex` table

### Scheduled Refresh

To update the local cache with recent changes from WoRMS, a refresh process is implemented. It identifies recently modified records in WoRMS and re-ingests them to keep the cache up-to-date.
The refresh can be run on demand or scheduled to run:

```
docker compose -f docker/docker-compose.yml run --rm api python manage.py refresh_worms
```

The flag `--dry-run` can be used to log which AphiaIDs would be refreshed without actually performing the refresh. The flag `--cache-ttl` can be used to specify a cutoff date for modified records (e.g., `--cache-ttl 7` to refresh records modified in the last 7 days). Refresh updates modified records, new taxa referenced in annotations, and rank updates if required.

## Development Workflow

Format code using Ruff:

```bash
docker compose -f docker/docker-compose.yml run --rm api tox -e format
```

Run lint checks:

```bash
docker compose -f docker/docker-compose.yml run --rm api tox -e lint
```

Run the test suite with coverage:

```bash
docker compose -f docker/docker-compose.yml run --rm api tox -e py313
```

Coverage reports are written to `coverage_reports/`.

## API Examples

A collection of example API requests and responses is available in the [API Examples](docs/API_EXAMPLES.md) document.

## Acknowledgements

This project was supported by the UK Natural Environment Research Council (NERC) through the *Tools for automating image analysis for biodiversity monitoring (AIAB)* Funding Opportunity, reference code **UKRI052**.
