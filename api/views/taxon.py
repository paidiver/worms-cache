"""ViewSet for the Taxon model."""

from typing import List  # noqa: UP035

from django.contrib.postgres.search import TrigramSimilarity
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import Taxon
from api.models.vernacular import Vernacular
from api.serializers.taxon import (
    ClassificationNodeSerializer,
    TaxonWormsLikeSerializer,
)
from api.services.filters import candidate_name_rows, rank_names_for_range
from api.services.taxamatch_client import TaxamatchError, match_batch

TAXAMATCH_LIMIT = 50
TOKENS_WITH_GENUS_SPECIES = 2


@extend_schema(tags=["Taxa"])
class TaxonViewSet(viewsets.ReadOnlyModelViewSet):
    """Taxa viewset class."""

    queryset = Taxon.objects.all()
    serializer_class = TaxonWormsLikeSerializer
    lookup_field = "aphia_id"

    def get_serializer_class(self):
        """Return the appropriate serializer class based on the action."""
        if self.action == "retrieve":
            return TaxonWormsLikeSerializer
        return TaxonWormsLikeSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scientific_name",
                type=str,
                required=False,
                description="Substring match against scientific name.",
            ),
            OpenApiParameter(
                name="rank",
                type=str,
                required=False,
                description="Optional rank filter (e.g. Species, Genus). Case-insensitive exact match.",
            ),
        ],
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        """List taxa, optionally filtered by query parameters."""
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """Filter the Taxon queryset by a provided taxon AphiaID (resolving synonyms) and/or language code."""
        qs = super().get_queryset().select_related("parent", "valid_taxon")

        scientific_name = (self.request.query_params.get("scientific_name") or "").strip()
        rank = (self.request.query_params.get("rank") or "").strip()

        if scientific_name:
            qs = qs.filter(scientific_name__icontains=scientific_name)

        if rank:
            qs = qs.filter(rank__iexact=rank)

        return qs.order_by("scientific_name")[:50]

    def get_object(self, only_valid: bool = False) -> Taxon:
        """Return the  taxon.

        Args:
            only_valid: If true, resolve the given AphiaID to its valid taxon if it is a synonym, otherwise return the
        taxon corresponding to the given AphiaID even if it is a synonym.

        Returns:
            The Taxon instance corresponding to the given AphiaID, resolving synonyms to their valid taxon if necessary.
        """
        aphia_id_raw = self.kwargs.get(self.lookup_field) or self.kwargs.get("pk")
        try:
            aphia_id = int(aphia_id_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError({"aphia_id": "Must be an integer AphiaID."}) from e

        base_qs = Taxon.objects.select_related("parent", "valid_taxon").prefetch_related("vernaculars")

        taxon = base_qs.filter(aphia_id=aphia_id).first()
        if taxon:
            if taxon.valid_taxon_id and taxon.valid_taxon_id != aphia_id and only_valid:
                valid = base_qs.filter(aphia_id=taxon.valid_taxon_id).first()
                return valid
            return taxon
        raise NotFound(detail=f"Valid taxon not found for AphiaID={aphia_id}")

    def _build_classification_tree(self, leaf: Taxon) -> dict:
        """Build WoRMS-style nested classification structure. Output keys: AphiaID, rank, scientificname, child.

        Args:
            leaf: The Taxon instance to build the classification tree for, typically the resolved valid taxon
        for a given AphiaID

        Returns:
            A nested dictionary representing the classification chain from root to the given leaf taxon in
        WoRMS API format
        """
        chain = []
        cur = leaf
        while cur is not None:
            chain.append(cur)
            cur = cur.parent
        chain.reverse()

        node = None
        for t in reversed(chain):
            node = {
                "AphiaID": t.aphia_id,
                "rank": t.rank,
                "scientificname": t.scientific_name,
                "child": node,
            }
        return node

    @extend_schema(responses={200: ClassificationNodeSerializer})
    @action(
        detail=False,
        methods=["get"],
        url_path=r"classification/(?P<aphia_id>\d+)",
    )
    def classification(self, request: Request, aphia_id=None) -> Response:
        """Return WoRMS-style nested classification object for a given AphiaID.

        Args:
            request: The HTTP request object.
            aphia_id: The AphiaID for which to retrieve the classification chain, passed as a URL parameter.

        Returns:
            A Response object containing a nested dictionary representing the classification chain from root to the
        given taxon in WoRMS API format, or a 404 if the taxon is not found.
        """
        taxon = self.get_object()
        tree = self._build_classification_tree(taxon)
        return Response(tree)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"synonyms/(?P<aphia_id>\d+)",
    )
    def synonyms(self, request: Request, aphia_id=None) -> Response:
        """Return synonyms for the resolved valid taxon.

        Args:
            request: The HTTP request object.
            aphia_id: The AphiaID for which to retrieve synonyms, passed as a URL parameter.

        Returns:
            A Response object containing a list of synonyms for the resolved valid taxon, or a 404 if the taxon
        is not found.
        """
        taxon = self.get_object(only_valid=True)
        syns = taxon.synonyms.all()
        return Response(TaxonWormsLikeSerializer(syns, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(name="NamePart", type=OpenApiTypes.STR, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(
                name="rank_min", type=OpenApiTypes.INT, required=False, description="Min rank (WoRMS-style integer)."
            ),
            OpenApiParameter(
                name="rank_max", type=OpenApiTypes.INT, required=False, description="Max rank (WoRMS-style integer)."
            ),
            OpenApiParameter(
                name="max_matches", type=OpenApiTypes.INT, required=False, description="Default 20, max 50."
            ),
            OpenApiParameter(name="excluded_ids[]", type=OpenApiTypes.INT, many=True, required=False),
            OpenApiParameter(
                name="combine_vernaculars",
                type=OpenApiTypes.BOOL,
                required=False,
                description="Include vernacular matching.",
            ),
            OpenApiParameter(
                name="languages[]",
                type=OpenApiTypes.STR,
                many=True,
                required=False,
                description="ISO639-3 codes, e.g. eng,nld,fra",
            ),
        ],
        responses={200: TaxonWormsLikeSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path=r"ajax_by_name_part/(?P<NamePart>[^/]+)")
    def ajax_by_name_part(self, request: Request, NamePart: str) -> Response:
        """Endpoint for AJAX autocomplete of taxon names.

        Args:
            request: The HTTP request object, expected to contain query parameters for filtering and matching options.
            NamePart: The path parameter containing the partial name to match against taxon scientific names.

        Returns:
            A Response object containing a list of matched taxa serialized in a WoRMS-like format, or a 204 No Content
        if no matches are found.
        """
        name_part = (NamePart or "").strip()
        if not name_part:
            return Response(status=204)

        max_matches, rank_min, rank_max, excluded, combine_vernaculars, languages = (
            self._validate_ajax_by_name_part_params(request)
        )
        rank_names = rank_names_for_range(rank_min, rank_max)

        scientific_taxon_ids = _handle_scientific_name_input_and_candidates(
            name_part,
            rank_names,
        )
        vern_taxon_ids = _handle_vernacular_matches(name_part, rank_names, combine_vernaculars, languages, max_matches)
        combined_ids = scientific_taxon_ids + vern_taxon_ids
        combined_taxa = list(Taxon.objects.filter(aphia_id__in=combined_ids).select_related("parent", "valid_taxon"))
        combined_taxa = _combine_taxa_list(combined_taxa, excluded, max_matches)
        if not combined_taxa:
            return Response(status=204)

        resolved = []
        seen_valid = set()
        for taxon in combined_taxa:
            valid_taxon = taxon.valid_taxon if taxon.valid_taxon_id else taxon
            if valid_taxon.aphia_id in seen_valid:
                continue
            seen_valid.add(valid_taxon.aphia_id)
            resolved.append(valid_taxon)
            if len(resolved) >= max_matches:
                break

        if not resolved:
            return Response(status=204)

        return Response(TaxonWormsLikeSerializer(resolved, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scientificnames[]",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                many=True,
                required=True,
                description="List of scientific names to match",
            ),
            OpenApiParameter(
                name="max_results",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Maximum matches per input (default 3)",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/TaxonWormsLike"},
                    },
                },
                description="List of match lists, one list per input scientific name",
            )
        },
    )
    @action(detail=False, methods=["get"], url_path="match_names")
    def match_names(self, request: Request) -> Response:  # noqa: C901
        """Match a query names against the Taxons using candidate + TAXAMATCH fuzzy matching algorithm by Tony Rees.

        Args:
            request: The HTTP request object, expected to contain a JSON body with a "names" key (list of strings)
            and optional "max_results" key (integer, default 3) to limit the number of matches returned per query name.

        Returns:
            A Response object containing a list of results for each matched taxa (up to max_results).
        """
        names = request.query_params.getlist("scientificnames[]")
        max_results = int(request.query_params.get("max_results", 3))
        if len(names) > TAXAMATCH_LIMIT:
            raise ValidationError({"names": f"Maximum {TAXAMATCH_LIMIT} names per call."})

        per_input = []
        for raw in names:
            qname = (raw or "").strip()
            candidate_rows = candidate_name_rows(qname, limit=300)
            qname = _handle_scientific_name_input(qname)
            per_input.append({"input": qname, "candidates": candidate_rows})

        batch_queries = []
        batch_to_input_idx = []

        for i, item in enumerate(per_input):
            if item["candidates"]:
                batch_queries.append(
                    {
                        "input": item["input"],
                        "candidates": [{"id": r.id, "name": r.name_raw} for r in item["candidates"]],
                    }
                )
                batch_to_input_idx.append(i)

        matched_ids_by_input_idx: dict[int, set[int]] = {}
        if batch_queries:
            try:
                batch_results = match_batch(batch_queries, timeout=3.0)
            except TaxamatchError:
                batch_results = []

            for j, br in enumerate(batch_results):
                input_idx = batch_to_input_idx[j]
                matched_ids_by_input_idx[input_idx] = set(br.get("matched_ids") or [])

        results = self._handle_taxamatch_names(per_input, max_results, matched_ids_by_input_idx)

        if all(len(r) == 0 for r in results):
            return Response(status=204)
        return Response(results)

    def _validate_ajax_by_name_part_params(self, request: Request) -> tuple[int, int, int, set[int], bool, List[str]]:  # noqa: UP006
        """Validate and parse query parameters for the ajax_by_name_part endpoint.

        Args:
            request: The HTTP request object containing the query parameters.

        Returns:
            A tuple containing the parsed and validated parameters: max_matches, rank_min, rank_max,
        excluded_ids, combine_vernaculars, languages
        """
        max_matches = int(request.query_params.get("max_matches", 20))
        max_matches = min(max_matches, 50)

        rank_min = int(request.query_params.get("rank_min", 0))
        rank_max = int(request.query_params.get("rank_max", 0))

        excluded = set()
        for x in request.query_params.getlist("excluded_ids[]"):
            try:
                excluded.add(int(x))
            except ValueError:
                continue

        combine_vernaculars = str(request.query_params.get("combine_vernaculars", "false")).lower() in (
            "1",
            "true",
            "yes",
        )
        languages = [x.strip().lower() for x in request.query_params.getlist("languages[]") if x.strip()]
        return max_matches, rank_min, rank_max, excluded, combine_vernaculars, languages

    def _handle_taxamatch_names(
        self,
        per_input: List[dict],  # noqa: UP006
        max_results: int,
        matched_ids_by_input_idx: dict[int, set[int]],
    ) -> List[dict]:  # noqa: UP006
        """Handle a single query name for the match_names endpoint, appending results to the output list.

        Args:
            per_input: The list of input items with their candidate rows and token counts, as prepared for the
        match_names endpoint.
            max_results: The maximum number of matched taxa to return for this query name.
            matched_ids_by_input_idx: A mapping from the index of the input item in per_input to the set of matched
        NameIndex ids.

        Returns:
            A list of result dictionaries for each query name, containing the input name and a list of matched taxa.
        """
        results = []
        for i, item in enumerate(per_input):
            qname = item["input"]
            candidates = item["candidates"]

            if not qname or not candidates:
                results.append([])
                continue

            matched_ids = matched_ids_by_input_idx.get(i, set())
            matched_rows = [c for c in candidates if c.id in matched_ids]

            if not matched_rows:
                results.append([])
                continue

            taxon_ids_in_order = []
            seen = set()
            for row in matched_rows:
                if row.taxon_id not in seen:
                    seen.add(row.taxon_id)
                    taxon_ids_in_order.append(row.taxon_id)

            taxa = list(Taxon.objects.filter(aphia_id__in=taxon_ids_in_order).select_related("parent", "valid_taxon"))
            taxa_by_id = {taxon.aphia_id: taxon for taxon in taxa}
            ordered_taxa = [taxa_by_id[tid] for tid in taxon_ids_in_order if tid in taxa_by_id]

            resolved = _handle_resolved_taxa(ordered_taxa, max_results)

            results.append(TaxonWormsLikeSerializer(resolved, many=True).data)

        return results

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scientificname1",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="The first scientific name to match",
            ),
            OpenApiParameter(
                name="scientificname2",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="The second scientific name to match",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {"match": {"type": "boolean"}},
                },
                description="Indicates whether the two scientific names match the same taxon",
            )
        },
    )
    @action(detail=False, methods=["get"], url_path="match_names_pair")
    def match_names_pair(self, request: Request) -> Response:
        """Check if two scientific names match the same taxon using the TaxaMatch service.

        Args:
            request: The HTTP request object, expected to contain query parameters "scientificname1" and
        "scientificname2"
        for the two names to compare,

        Returns:
            A Response object true if the two names match the same taxon according to TaxaMatch, false otherwise.
        """
        scientific_name1 = _handle_scientific_name_input(request.query_params.get("scientificname1", ""))
        scientific_name2 = _handle_scientific_name_input(request.query_params.get("scientificname2", ""))

        batch_queries = [{"input": scientific_name1, "candidates": [{"id": 1, "name": scientific_name2}]}]
        batch_results = match_batch(batch_queries, timeout=3.0)

        matched_ids = batch_results[0].get("matched_ids", [])
        match = False
        if matched_ids:
            match = len(matched_ids) > 0
        return Response({"match": match})


def _handle_scientific_name_input(name: str) -> str:
    """Handle and normalize scientific name input for the match_names_pair endpoint.

    Args:
        name: The raw scientific name input string.

    Returns:
        A normalized scientific name string suitable for matching, or an empty string if the input is invalid
    """
    name = (name or "").strip()
    tokens = name.split()

    if len(tokens) >= TOKENS_WITH_GENUS_SPECIES:
        tokens[0] = tokens[0].capitalize()
        return " ".join(tokens)

    return name


def _dedupe_keep_order(ids: list[int]) -> list[int]:
    """Deduplicate a list of integers while preserving order.

    Args:
        ids: A list of integers that may contain duplicates.

    Returns:
        A new list of integers with duplicates removed, preserving the original order of first occurrence.
    """
    return list(dict.fromkeys(ids))


def _handle_resolved_taxa(taxa: list[Taxon], max_results: int) -> list[Taxon]:
    """Handle resolving a list of Taxon instances to their valid taxa, preserving order and limiting results.

    Args:
        taxa: A list of Taxon instances to resolve.
        max_results: The maximum number of resolved valid taxa to return.

    Returns:
        A list of resolved valid Taxon instances, preserving the order of the input taxa and limited
    to max_results.
    """
    resolved = []
    seen_valid_ids = set()
    for taxon in taxa:
        valid_taxon = taxon.valid_taxon if taxon.valid_taxon_id else taxon
        if valid_taxon.aphia_id in seen_valid_ids:
            continue
        seen_valid_ids.add(valid_taxon.aphia_id)
        resolved.append(valid_taxon)

        if len(resolved) >= max_results:
            break
    return resolved


def _handle_scientific_name_input_and_candidates(
    name_part: str,
    rank_names: set[str] | None,
) -> list[int]:
    """Handle the scientific name input and candidate retrieval for the ajax_by_name_part endpoint.

    Args:
        name_part: The raw scientific name part to match against taxon names.
        rank_names: An optional set of rank names to filter candidates by.

    Returns:
        A list of AphiaIDs for taxa that match the given scientific name part and filtering criteria
    """
    candidate_rows = candidate_name_rows(name_part, limit=300, rank_names=rank_names)

    scientific_taxon_ids: list[int] = []
    if candidate_rows:
        normalized = _handle_scientific_name_input(name_part)

        try:
            batch_results = match_batch(
                [
                    {
                        "input": normalized,
                        "candidates": [{"id": r.id, "name": r.name_raw} for r in candidate_rows],
                    }
                ],
                timeout=3.0,
            )
            matched_candidate_ids = set((batch_results[0] or {}).get("matched_ids") or [])
            if matched_candidate_ids:
                scientific_taxon_ids = _dedupe_keep_order(
                    [r.taxon_id for r in candidate_rows if r.id in matched_candidate_ids]
                )
            else:
                scientific_taxon_ids = _dedupe_keep_order([r.taxon_id for r in candidate_rows])

        except TaxamatchError:
            scientific_taxon_ids = _dedupe_keep_order([r.taxon_id for r in candidate_rows])
    return scientific_taxon_ids


def _handle_vernacular_matches(
    name_part: str,
    rank_names: set[str] | None,
    combine_vernaculars: bool,
    languages: list[str],
    max_matches: int,
) -> list[int]:
    """Handle vernacular name matching for the ajax_by_name_part endpoint.

    Args:
        name_part: The raw name part to match against vernacular names.
        rank_names: An optional set of rank names to filter candidates by.
        combine_vernaculars: Whether to include vernacular matches in the results.
        languages: A list of ISO639-3 language codes to filter vernacular names by.
        max_matches: The maximum number of matches to return, used to limit number of vernacular candidates processed.

    Returns:
        A list of AphiaIDs for taxa that match the given name part in their vernacular names, filtered by the given
    criteria.
    """
    vern_taxon_ids: list[int] = []
    if combine_vernaculars:
        vernacular_query_set = Vernacular.objects.all()

        if languages:
            vernacular_query_set = vernacular_query_set.filter(language_code__in=languages)

        if rank_names is not None:
            vernacular_query_set = vernacular_query_set.filter(taxon__rank__in=rank_names)

        vern_taxon_ids = list(
            vernacular_query_set.annotate(sim=TrigramSimilarity("name", name_part))
            .filter(sim__gt=0.2)
            .order_by("-sim")
            .values_list("taxon_id", flat=True)
            .distinct()[: max_matches * 2]
        )
    return vern_taxon_ids


def _combine_taxa_list(
    taxa: list[Taxon],
    excluded: set[int],
    max_matches: int,
) -> list[int]:
    """Combine and deduplicate scientific and vernacular taxon ID lists, applying exclusions and limits.

    Args:
        taxa: A list of Taxon objects to combine.
        excluded: A set of AphiaIDs to exclude from the results.
        max_matches: The maximum number of combined matches to return.

    Returns:
        A list of Taxon objects, excluding any in the excluded set and limited to max_matches.
    """
    filtered_combined_taxa = []
    seen = set()
    for taxon in taxa:
        taxon_id = taxon.aphia_id
        taxon_valid_id = taxon.valid_taxon_id if taxon.valid_taxon_id else taxon.aphia_id
        if taxon_id in excluded or taxon_valid_id in excluded:
            continue
        if taxon_id in seen:
            continue
        seen.add(taxon_id)
        filtered_combined_taxa.append(taxon)
        if len(filtered_combined_taxa) >= max_matches:
            break
    return filtered_combined_taxa
