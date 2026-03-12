# API Examples

Set your API base URL once:

```bash
export API_BASE="http://localhost:8000"
```

## Taxa

### Ingest new AphiaID

For this endpoint, you need to provide a valid token in the `Authorization` header. You can set this token as an environment variable and use it in your curl command:

```bash
curl -X POST "$API_BASE/api/taxa/ingest/" \
  -H "Authorization: Bearer mysecrettoken" \
  -H "Content-Type: application/json" \
  -d '{"aphia_id": 12345}'
```

If the AphiaID is successfully ingested, you will receive a response with the taxon data and a 202 Accepted status. If the AphiaID is already in the database or invalid, you will get a 400 Bad Request response with an error message.

### List

```
curl "$API_BASE/api/taxa/?scientific_name=Asterias&rank=Species"
```

Query params:

* `scientific_name`
* `rank`


### Retrieve

```
curl "$API_BASE/api/taxa/{aphia_id}/"
```

Resolves synonyms automatically.


## Classification

```
curl "$API_BASE/api/taxa/classification/{aphia_id}/"
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

## Synonyms

```
curl "$API_BASE/api/taxa/synonyms/{aphia_id}/"
```

It will return all synonyms for the given AphiaID, including the accepted name if the input is a synonym. Each synonym record includes all the information from the `taxa` table.


## AJAX Autocomplete

```
curl "$API_BASE/api/taxa/ajax_by_name_part/{NamePart}/"
```
Query param:
* `NamePart` → partial name string for autocomplete
* Optional:
  * `min_rank` → filter results by rank
  * `max_rank` → filter results by rank
  * `include_vernaculars=true` → include vernacular names in results
  * `max_results=20` → limit number of results (default 20, max 100)
  * `languages=eng` → filter vernaculars by language code (e.g. 'eng' for English)
  * `excluded_ids=1` → a list of AphiaIDs to exclude from results

## Batch Scientific Name Matching

```
curl -X POST "$API_BASE/api/taxa/match_names/?scientificnames[]=Asterias rubens&scientificnames[]=Asterias&scientificnames[]=InvalidName"
```
Query params:
* `scientificnames[]` → array of scientific name strings to match

Uses:

1. Candidate narrowing via NameIndex
2. Fuzzy matching via Taxamatch microservice
3. Deduplicated valid taxa resolution

Limit: 50 names per request

---

## Pair Matching

```
curl "$API_BASE/api/taxa/match_names_pair?scientificname1=Asterias rubens&scientificname2=Asterias rubens"
```

Returns:

```json
{ "match": true }
```

---

## Vernaculars

### List

```
curl "$API_BASE/api/vernaculars/"
```

It returns all vernacular names with their associated AphiaIDs and language codes.

### Retrieve

```
curl "$API_BASE/api/vernaculars/{aphia_id}/"
```

Query params:

* `language_code`
* `follow_valid=true`


---

## Ranks

### List

```
curl "$API_BASE/api/ranks/"
```

### Retrieve

```
curl "$API_BASE/api/ranks/{taxon_rank_name}/"
```

## Name Index

### List

```
curl "$API_BASE/api/name_index/"
```

This will return all entries in the `NameIndex` table, which includes both accepted names and synonyms. This endpoint is primarily intended for debugging and development purposes, as the `NameIndex` is an internal optimization layer for fast name lookup and fuzzy matching.

### Retrieve

```
curl "$API_BASE/api/name_index/{id}/"
```
