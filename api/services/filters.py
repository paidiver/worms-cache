"""Service for matching query names to candidate name rows in the NameIndex table."""

from django.contrib.postgres.search import TrigramSimilarity

from api.models.name_index import NameIndex
from api.models.rank import Rank
from api.utils.names import parse_genus_epithet


def rank_names_for_range(rank_min: int, rank_max: int) -> set[str] | None:
    """Get the set of rank names that fall within a specified rank range.

    Args:
        rank_min: The minimum rank value.
        rank_max: The maximum rank value.

    Returns:
        A set of rank names that fall within the specified rank range, or None if no filtering is needed.
    """
    if rank_min == 0 and rank_max == 0:
        return None
    if rank_min > 0 and rank_max > 0 and rank_min > rank_max:
        raise ValueError("rank_min cannot be greater than rank_max")

    qs = Rank.objects.all()
    if rank_min > 0:
        qs = qs.filter(rank_id__gte=rank_min)
    if rank_max > 0:
        qs = qs.filter(rank_id__lte=rank_max)

    return set(qs.values_list("name", flat=True))


def candidate_name_rows(query_name: str, limit: int = 300, rank_names: set[str] | None = None) -> list[NameIndex]:
    """Find candidate name rows in the NameIndex table that are similar to the query name.

    Args:
        query_name: The raw scientific name string to be matched against the NameIndex.
        limit: The maximum number of candidate rows to return.
        rank_names: An optional set of rank names to filter the candidate rows by. If None, no filtering is applied.

    Returns:
        A list of NameIndex rows that are similar to the query name.
    """
    parsed = parse_genus_epithet(query_name)
    tokens = parsed.canonical_norm.split()

    base = NameIndex.objects.all()

    if rank_names is not None:
        base = base.filter(taxon__rank__in=rank_names)

    base = base.select_related("taxon")

    if len(tokens) == 1:
        if parsed.genus_prefix3:
            query_set = base.filter(genus_prefix3=parsed.genus_prefix3)
        elif parsed.genus_prefix2:
            query_set = base.filter(genus_prefix2=parsed.genus_prefix2)
        else:
            query_set = base

        query_set = (
            query_set.annotate(sim=TrigramSimilarity("genus_norm", parsed.genus_norm))
            .filter(sim__gt=0.2)
            .order_by("-sim")[:limit]
        )
        rows = list(query_set)
        if rows:
            return rows

        query_set = (
            base.annotate(sim=TrigramSimilarity("canonical_norm", parsed.canonical_norm))
            .filter(sim__gt=0.2)
            .order_by("-sim")[:limit]
        )
        return list(query_set)

    if parsed.genus_norm:
        query_set = (
            base.filter(genus_norm=parsed.genus_norm)
            .annotate(sim=TrigramSimilarity("canonical_norm", parsed.canonical_norm))
            .filter(sim__gt=0.2)
            .order_by("-sim")[:limit]
        )
        rows = list(query_set)
        if rows:
            return rows

    if parsed.genus_prefix3:
        query_set = (
            base.filter(genus_prefix3=parsed.genus_prefix3)
            .annotate(sim=TrigramSimilarity("canonical_norm", parsed.canonical_norm))
            .filter(sim__gt=0.2)
            .order_by("-sim")[:limit]
        )
        rows = list(query_set)
        if rows:
            return rows

    query_set = (
        base.annotate(sim=TrigramSimilarity("canonical_norm", parsed.canonical_norm))
        .filter(sim__gt=0.2)
        .order_by("-sim")[:limit]
    )
    return list(query_set)
