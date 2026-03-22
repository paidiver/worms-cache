"""Service to rebuild the NameIndex table from the Taxon table."""

import logging

from django.db import transaction

from api.models import Taxon
from api.models.name_index import NameIndex, NameType
from api.utils.names import parse_genus_epithet

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5000


def rebuild_name_index(aphia_ids: list[int] | None = None):
    """Rebuild the NameIndex table from the Taxon table.

    Args:
        aphia_ids: Optional list of AphiaIDs to rebuild the NameIndex for. If None, the NameIndex will be rebuilt for
    all taxa.
    """
    logger.info("Starting rebuild of NameIndex from Taxon data")
    with transaction.atomic():
        if aphia_ids is not None:
            NameIndex.objects.filter(taxon_id__in=aphia_ids).delete()
            taxa_iterator = (
                Taxon.objects.filter(aphia_id__in=aphia_ids)
                .only("aphia_id", "scientific_name")
                .iterator(chunk_size=CHUNK_SIZE)
            )
        else:
            NameIndex.objects.all().delete()
            taxa_iterator = Taxon.objects.all().only("aphia_id", "scientific_name").iterator(chunk_size=CHUNK_SIZE)
        batch = []
        for taxon in taxa_iterator:
            batch = generate_name_index_entries_for_taxon(taxon, batch)
            if len(batch) >= CHUNK_SIZE:
                NameIndex.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []
        if batch:
            NameIndex.objects.bulk_create(batch, ignore_conflicts=True)
    logger.info("Finished rebuild of NameIndex")


def generate_name_index_entries_for_taxon(taxon: Taxon, batch: list[NameIndex]) -> list[NameIndex]:
    """Generate NameIndex entries for a given Taxon and add them to the batch list.

    Args:
        taxon: The Taxon for which to generate NameIndex entries.
        batch: The current batch list to which new NameIndex entries will be added.

    Returns:
        The updated batch list with new NameIndex entries added.
    """
    parsed = parse_genus_epithet(taxon.scientific_name)
    batch.append(
        NameIndex(
            taxon_id=taxon.aphia_id,
            name_type=NameType.ACCEPTED,
            name_raw=taxon.scientific_name,
            canonical_norm=parsed.canonical_norm,
            genus_norm=parsed.genus_norm,
            epithet_norm=parsed.epithet_norm,
            genus_prefix2=parsed.genus_prefix2,
            genus_prefix3=parsed.genus_prefix3,
            canon_prefix3=parsed.canon_prefix3,
        )
    )
    if taxon.aphia_id != taxon.valid_taxon_id and taxon.valid_taxon_id is not None:
        batch.append(
            NameIndex(
                taxon_id=taxon.valid_taxon_id,
                name_type=NameType.SYNONYM,
                name_raw=taxon.scientific_name,
                canonical_norm=parsed.canonical_norm,
                genus_norm=parsed.genus_norm,
                epithet_norm=parsed.epithet_norm,
                genus_prefix2=parsed.genus_prefix2,
                genus_prefix3=parsed.genus_prefix3,
                canon_prefix3=parsed.canon_prefix3,
            )
        )
    return batch
