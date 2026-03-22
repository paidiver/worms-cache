# API Examples

Set your API base URL once:

```bash
export API_BASE="http://localhost:8000"
```

---

## Taxa

### Ingest new AphiaID

This endpoint requires a valid bearer token in the `Authorization` header.

```bash
curl -X POST "$API_BASE/api/taxa/ingest/" \
  -H "Authorization: Bearer mysecrettoken" \
  -H "Content-Type: application/json" \
  -d '{"aphia_id": 12345}'
```

Behavior:

* `202 Accepted` → AphiaID was newly ingested
* `200 OK` → AphiaID already exists in the local database
* `400 Bad Request` → invalid input or ingestion failed
* `401 Unauthorized` → missing or invalid token

Response format:

```json
[
  {
    "AphiaID": 12345,
    "scientificname": "Example taxon",
    "rank": "Species"
  }
]
```

Note: the response is a list of taxa, not a single object.

### List taxa

```bash
curl "$API_BASE/api/taxa/?scientific_name=Asterias&rank=Species"
```
You can also request a specific set of AphiaIDs:

```bash
curl "$API_BASE/api/taxa/?aphia_ids[]=123&aphia_ids[]=456"
```

Query params:

* `scientific_name` → substring match against `scientific_name`
* `rank` → case-insensitive exact rank match (for example `Species`, `Genus`)
* `aphia_ids[]` → list of AphiaIDs to return directly

Notes:
* Results are ordered by `scientific_name`
* General list responses are limited to 50 results


### List AphiaIDs including descendants

Returns the provided AphiaIDs plus all descendant AphiaIDs.

```bash
curl "$API_BASE/api/taxa/ids_with_descendants/?aphia_ids[]=123&aphia_ids[]=456"
```

Query params:

* `aphia_ids[]` → required list of AphiaIDs

Response format:

```json
[123, 124, 125, 456, 457]
```

If no valid AphiaIDs are provided, the API returns 400.

### Retrieve taxon

```bash
curl "$API_BASE/api/taxa/{aphia_id}/"
```

Query params:

* `only_valid=true` → if true, returns the accepted taxon instead of the synonym if the input AphiaID is a synonym
* `include_descendants=true` → if true, includes all descendant taxa in the response
* `include_parents=true` → if true, includes all parent taxa up to the root


Response format:

```json
{
  "taxon": {
    "AphiaID": 1,
    "scientificname": "Animalia",
    "rank": "Kingdom",
    ...
  },
"parents": [
    {
      "AphiaID": 2,
      "scientificname": "Eukaryota",
      "rank": "Domain",
      ...
    },
    ...
  ],
  "descendants": [
    {
      "AphiaID": 3,
      "scientificname": "Chordata",
      "rank": "Phylum",
      ...
    },
    ...
  ]
}
```

Parents and descendants are only included if the corresponding query parameters are set to true. If the taxon is not found, a 404 Not Found response is returned.

---

## Classification

Returns a nested WoRMS-style classification tree for the given AphiaID.

```bash
curl "$API_BASE/api/taxa/classification/{aphia_id}/"
```

Response format:

```json
{
  "AphiaID": 1,
  "rank": "Kingdom",
  "scientificname": "Animalia",
  "child": {
    "AphiaID": 2,
    "rank": "Phylum",
    "scientificname": "Chordata",
    "child": {
      "AphiaID": 3,
      "rank": "Class",
      "scientificname": "Actinopterygii",
      "child": null
    }
  }
}
```

---

## Synonyms

Returns synonyms for the resolved valid taxon.

```bash
curl "$API_BASE/api/taxa/synonyms/{aphia_id}/"
```

Behavior:

* if the input AphiaID is a synonym, it is first resolved to the valid taxon
* the response contains the synonym taxa associated with that valid taxon

Response format:

```json
[
  {
    "AphiaID": 111,
    "scientificname": "Old name example",
    "rank": "Species"
  }
]
```

---

## AJAX Autocomplete

### Full taxon objects

```bash
curl "$API_BASE/api/taxa/ajax_by_name_part/{name_part}/"
```
Query param:
* `name_part` → partial name string for autocomplete
* Optional:
  * `min_rank` → filter results by rank
  * `max_rank` → filter results by rank
  * `include_vernaculars=true` → include vernacular names in results
  * `max_results=20` → limit number of results (default 20, max 100)
  * `languages[]=eng&languages[]=fra` → filter vernacular matching by ISO639-3 language code
  * `excluded_ids[]=123&excluded_ids[]=456` → AphiaIDs to exclude

Example:

```bash
curl "$API_BASE/api/taxa/ajax_by_name_part/asterias/?combine_vernaculars=true&languages[]=eng&max_matches=10"
```

Behavior:

* returns matched taxa in WoRMS-like format
* resolves synonyms to valid taxa
* deduplicates results by valid AphiaID
* returns `204 No Content` if nothing matches

### Only AphiaIDs

Same matching logic as above, but returns only AphiaIDs.

```bash
curl "$API_BASE/api/taxa/ajax_by_name_part/only_ids/asterias/"
```

Response format:

```json
[127160, 1371, 248099]
```

---

## Batch Scientific Name Matching

Matches one or more scientific names using candidate narrowing plus Taxamatch fuzzy matching.

```bash
curl -X POST "$API_BASE/api/taxa/match_names/?scientificnames[]=Asterias rubens&scientificnames[]=Asterias&scientificnames[]=InvalidName"
```
Query params:
* `scientificnames[]` → array of scientific name strings to match
* `max_results` → maximum matches per input name, default `3`

Response format:

```json
[
  [
    {
      "AphiaID": 123,
      "scientificname": "Asterias rubens",
      "rank": "Species"
    }
  ],
  [
    {
      "AphiaID": 456,
      "scientificname": "Asterias",
      "rank": "Genus"
    }
  ],
  []
]
```

Each top-level item corresponds to one input name, in the same order.

Behavior:

1. Candidate narrowing via internal name index
2. Fuzzy matching via Taxamatch
3. Resolution to valid taxa
4. Deduplication of valid matches
5. Limit: 50 names per request

---

## Pair Matching

Checks whether two scientific names match according to the Taxamatch service.

```bash
curl "$API_BASE/api/taxa/match_names_pair/?scientificname1=Asterias%20rubens&scientificname2=Asterias%20rubens"
```

Returns:

```json
{ "match": true }
```

Query params:

* `scientificname1` → first scientific name
* `scientificname2` → second scientific name

---

## Vernaculars

### List

```bash
curl "$API_BASE/api/vernaculars/"
```

Returns vernacular names with associated AphiaIDs and language codes.

### Retrieve

```bash
curl "$API_BASE/api/vernaculars/{aphia_id}/"
```

Query params:

* `language_code` → ISO639-3 language code
* `follow_valid=true` → follow valid taxa

---

## Ranks

### List

```bash
curl "$API_BASE/api/ranks/"
```

### Retrieve

```bash
curl "$API_BASE/api/ranks/{taxon_rank_name}/"
```

---

## Name Index

These endpoints are mainly intended for debugging and development.

### List

```bash
curl "$API_BASE/api/name_index/"
```

Returns entries from the internal `NameIndex` table, used for fast name lookup and fuzzy matching.

### Retrieve

```bash
curl "$API_BASE/api/name_index/{id}/"
```
