# API Examples

Set your API base URL once:

```bash
export API_BASE="http://localhost:8000"
```

## Create (POST)

### Field endpoints

You can see below some examples of how to create objects through the API for the field endpoints, that only need to provide a `name` field. You can also include `uri` if you want.

#### Context

```bash
curl -sS -X POST "$API_BASE/api/fields/context/" \
  -H "Content-Type: application/json" \
  -d '{"name": "test Context",
      "uri": "https://example.com/contexts/test-context"
      }'
  ```

#### PI

```bash
curl -sS -X POST "$API_BASE/api/fields/pi/" \
  -H "Content-Type: application/json" \
  -d '{"name": "test PI"}'
```

### RelatedMaterial

For related material, the `uri` field is required, but you can also include `title` and `relation` if you want.

```bash
curl -sS -X POST "$API_BASE/api/fields/relatedmaterial/" \
  -H "Content-Type: application/json" \
  -d '{"uri": "https://example.com/related-material/12345", "title": "Related material title", "relation": "isSupplementTo"
  }'
```

> Important: you may need to output IDs of created objects (e.g. related materials, context, pi) to use them in the examples below for creating ImageSets, AnnotationSets, etc. You can do this by running a GET request to the corresponding endpoint (e.g. `GET /api/fields/relatedmaterial/`) and looking for the ID in the response.

### ImageSet

`ImageSet` requires at least a `name`. This examples also demonstrate how to create related objects through relationships:

* **Many-to-many (M2M)** (e.g. `creators`):

  * Provide full objects (e.g. `{ "name": "..." }`) → the API creates them if needed
  * OR provide existing IDs via `creators_ids`

* **Foreign keys (FK)** (e.g. `project`):

  * Provide `project_id`
  * OR provide a full `project` object with the required fields

To run the example below, replace `RELATED_MATERIAL_ID` with an existing related material ID from your database, or provide a full `related_material` object instead.

```bash
RELATED_MATERIAL_ID="00000000-0000-0000-0000-000000000001"
curl -sS -X POST "$API_BASE/api/images/image_sets/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dive 2026-02-11",
    "handle": "https://handle.example/12345/abc",
    "creators": [
      {
        "name": "Dr. Jane Doe",
        "uri": "https://example.com/creators/jane-doe"
      }
    ],
    "related_materials_ids": [
      "'$RELATED_MATERIAL_ID'"
    ],
    "project": {
      "name": "Benthic survey 2026",
      "uri": "https://example.com/projects/benthic-survey-2026"
    }
  }'
```

This will result in the following objects being created:

* An `ImageSet` with the provided name and handle, linked to the project with ID `00000000-0000-0000-0000-000000000100`
* A `Creator` with the provided name and URI, linked to the `ImageSet` through an M2M relationship
* A `Project` with the provided name and URI, linked to the `ImageSet` through an FK relationship

### AnnotationSet

`AnnotationSet` requires at least a `name`. This examples also demonstrate how to create related objects through relationships. You must use existing `ImageSet` IDs from your database for the `image_set_ids` field. For the other M2M and FK relationships, the same rules apply as described in the `ImageSet` example above. In the example below, replace `project_id` with an existing project ID from your database, or provide a full `project` object instead. Also replace `image_set_ids` with existing `ImageSet` IDs from your database.

```bash
IMAGE_SET_ID="00000000-0000-0000-0000-000000000010"
PROJECT_ID="00000000-0000-0000-0000-000000000100"
curl -sS -X POST "$API_BASE/api/annotations/annotation_sets/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Benthic survey annotations (v1)",
    "version": "1.0.0",
    "image_set_ids": [
      "'$IMAGE_SET_ID'"
    ],
    "creators": [
      {
        "name": "Dr. Jane Doe",
        "uri": "https://example.com/creators/jane-doe"
      }
    ],
    "project_id": "'$PROJECT_ID'",
    "abstract": "Annotation set for the benthic imagery collected during survey XYZ."
  }'
```

This will create an `AnnotationSet` linked to the specified `ImageSet` and `Project`, with ID `00000000-0000-0000-0000-000000000020`. You can then use this `annotation_set_id` when creating `Annotation` objects to link annotations to this annotation set.

### Image

For the `Image` model, the following fields are required: `image_set_id` and `filename`. The `image_set_id` field must reference an existing `ImageSet` in your database. The `filename` should be a string representing the name of the image file (e.g. "dive2026-02-11_img001.jpg"). Replace the `image_set_id` value in the example below with an existing `ImageSet` ID from your database.

```bash
IMAGE_SET_ID="00000000-0000-0000-0000-000000000010"
curl -sS -X POST "$API_BASE/api/images/images/" \
  -H "Content-Type: application/json" \
  -d '{
    "image_set_id": "'$IMAGE_SET_ID'",
    "filename": "dive2026-02-11_img001.jpg"
  }'
```

This will create an `Image` linked to the specified `ImageSet`, with ID `00000000-0000-0000-0000-000000000001`. You can then use this `image_id` when creating `Annotation` objects to link annotations to this image.

### Annotation

For the `Annotation` model, the following fields are required: `shape` and `coordinates`. The `shape` field must be one of the allowed values (e.g. "polygon", "circle", etc.), and the `coordinates` field must be a list of lists, where each inner list represents a set of coordinates corresponding to the specified shape. For example, for a polygon shape, the coordinates would be a list of points (x, y) that define the vertices of the polygon.

This endpoint also requires the `annotation_set_id` and `image_id` fields to link the annotation to an existing `AnnotationSet` and `Image`. You must use IDs that exist in your database for these fields.

```bash
IMAGE_ID="00000000-0000-0000-0000-000000000001"
ANNOTATION_SET_ID="00000000-0000-0000-0000-000000000020"
curl -sS -X POST "$API_BASE/api/annotations/annotations/" \
  -H "Content-Type: application/json" \
  -d '{
    "annotation_set_id": "'$ANNOTATION_SET_ID'",
    "image_id": "'$IMAGE_ID'",
    "annotation_platform": "SQUIDLE+",
    "shape": "polygon",
    "coordinates": [
      [100.5, 120.0, 180.2, 125.1, 175.0, 210.6, 98.9, 205.3, 100.5, 120.0]
    ],
    "dimension_pixels": 92.4
  }'
```

This will create an `Annotation` linked to the specified `AnnotationSet` and `Image`, with ID `00000000-0000-0000-0000-000000000100`.

### Label

For the `Label` model, the following fields are required: `name` and `parent_label_name`. You also need to provide an existing `annotation_set_id` from your database to link the label to an `AnnotationSet`:

```bash
ANNOTATION_SET_ID="00000000-0000-0000-0000-000000000020"
curl -sS -X POST "$API_BASE/api/labels/labels/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "coral",
    "parent_label_name": "organism",
    "annotation_set_id": "'$ANNOTATION_SET_ID'"
  }'
```

This will create a `Label` with the specified name and parent label, linked to the specified `AnnotationSet`, with ID `00000000-0000-0000-0000-000000000002`. You can then use this `label_id` when creating `AnnotationLabel` objects to link annotations to this label.

### AnnotationLabel

For the `AnnotationLabel` model, the following fields are required: `creation_datetime`, `annotation_id` and `label_id`. You must use existing IDs from your database for these fields to link an existing `Annotation` to an existing `Label`.

For the `annotator` field, it applies the same rules described for `ImageSet`: you can either provide an existing `annotator_id` or a full `annotator` object with the required fields (e.g. `name`). If you provide a full `annotator` object and an annotator with the same name already exists in the database, it will link to the existing annotator instead of creating a new one.

```bash
ANNOTATION_ID="00000000-0000-0000-0000-000000000100"
LABEL_ID="00000000-0000-0000-0000-000000000002"
curl -sS -X POST "$API_BASE/api/annotations/annotation_labels/" \
  -H "Content-Type: application/json" \
  -d '{
    "annotation_id": "'$ANNOTATION_ID'",
    "label_id": "'$LABEL_ID'",
    "annotator": {
      "name": "Dr. Jane Doe"
    },
    "creation_datetime": "2026-02-15T10:30:00Z"
  }'
```

## Read (GET)


#### List Creator
```bash
curl -sS -X GET "$API_BASE/api/fields/creator/" -H "Accept: application/json"
```

#### List Context
```bash
curl -sS -X GET "$API_BASE/api/fields/context/" -H "Accept: application/json"
```

#### List PI
```bash
curl -sS -X GET "$API_BASE/api/fields/pi/" -H "Accept: application/json"
```

### List all Images

```bash
curl -sS "$API_BASE/api/images/images/"
```

### Retrieve a single Image

In the example below, replace `IMAGE_ID` with an existing image ID from your database.

```bash
IMAGE_ID="00000000-0000-0000-0000-000000000001"
curl -sS "$API_BASE/api/images/images/$IMAGE_ID/"
```

## Update (PUT)

### ImageSet

This replaces the entire object. You must include at least `name` and any fields you want to update; otherwise, they will be set to null or empty. For relationships:

* **M2M fields** (e.g. `related_materials_ids`, `creators_ids`):
  Provide the full updated list of IDs.
* **FK fields** (e.g. `project`):
  Provide either `project_id` or a full `project` object.

In the example below, replace `IMAGE_SET_ID` with an existing image set ID from your database. For `creators_ids`, replace them with existing IDs from your database or remove the field if you do not want to update it. For `project`, you can either provide an existing `project_id` or a full `project` object with the required fields.

```bash
IMAGE_SET_ID="00000000-0000-0000-0000-000000000010"
CREATOR_ID="4f545b61-4c4a-47ed-b9f9-a59d72dcfcb9"
curl -sS -X PUT "$API_BASE/api/images/image_sets/$IMAGE_SET_ID/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dive 2026-02-11 (processed)",
    "handle": "https://handle.example/12345/abc",
    "copyright": "© NOC",
    "abstract": "Images collected during the dive on 2026-02-11. This record was updated after QC.",
    "creators_ids": [
      "'$CREATOR_ID'"
    ],
    "project": {
      "name": "Benthic survey 2026",
      "uri": "https://example.com/projects/benthic-survey-2026"
    },
    "min_latitude_degrees": 49.95,
    "max_latitude_degrees": 50.10,
    "min_longitude_degrees": -4.20,
    "max_longitude_degrees": -4.05
  }'
```

## Delete (DELETE)

### Delete a Label

In the example below, replace `LABEL_ID` with an existing label ID from your database.

```bash
LABEL_ID="00000000-0000-0000-0000-000000000002"

curl -sS -X DELETE "$API_BASE/api/labels/labels/$LABEL_ID/"
```
