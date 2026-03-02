"""Service to rebuild the NameIndex table from the Taxon table."""

import logging

from django.db import transaction

from api.models import Taxon
from api.models.name_index import NameIndex, NameType
from api.utils.names import parse_genus_epithet

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5000


def rebuild_name_index():
    """Rebuild the NameIndex table from the Taxon table."""
    logger.info("Starting rebuild of NameIndex from Taxon data")
    with transaction.atomic():
        NameIndex.objects.all().delete()

        batch = []

        for taxon in Taxon.objects.all().only("aphia_id", "scientific_name").iterator(chunk_size=CHUNK_SIZE):
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
            if len(batch) >= CHUNK_SIZE:
                NameIndex.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []
        if batch:
            NameIndex.objects.bulk_create(batch, ignore_conflicts=True)
    logger.info("Finished rebuild of NameIndex")
