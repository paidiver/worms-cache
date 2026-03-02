"""Django management command to rebuild the NameIndex table from the Taxon table."""

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Taxon
from api.models.name_index import NameIndex, NameType
from api.utils.names import parse_genus_epithet

CHUNK_SIZE = 5000


class Command(BaseCommand):
    """Django management command to rebuild the NameIndex table from the Taxon table."""

    help = "Rebuild name_index table from Taxon table."

    def handle(self, *args, **options):
        """Handle the command execution.

        Args:
            *args: Positional arguments (not used).
            **options: Command-line options (not used).
        """
        self.stdout.write("Rebuilding name_index...")
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

        self.stdout.write(self.style.SUCCESS("Done."))
