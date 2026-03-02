"""Django management command to refresh cached WoRMS taxa that are stale or "hot" (recently accessed)."""

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import Taxon
from api.services.cache_policy import is_stale
from api.services.ingest_aphia_id import ingest_aphia_id


class Command(BaseCommand):
    """Django management command to refresh cached WoRMS taxa that are stale or "hot" (recently accessed)."""

    help = "Refresh cached WoRMS taxa that are stale (optionally only hot taxa)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command-line arguments.

        Args:
            parser: The argument parser to which command-line arguments can be added.
        """
        parser.add_argument(
            "--hot-days", type=int, default=30, help="Consider taxa accessed within the last N days as 'hot'."
        )
        parser.add_argument("--limit", type=int, default=1000, help="Max number of taxa to refresh.")
        parser.add_argument("--force", action="store_true", help="Refresh even if not stale.")
        parser.add_argument(
            "--strategy",
            choices=["recent", "top"],
            default="recent",
            help="Which hot-list strategy to use: recent access or top access_count.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be refreshed without making changes."
        )

    def handle(self, *args, **opts):
        """Handle the command execution.

        Args:
            *args: Positional arguments (not used).
            **opts: Command-line options, including "ids" which is a list of AphiaIDs to ingest.
        """
        hot_days = opts["hot_days"]
        limit = opts["limit"]
        force = opts["force"]
        strategy = opts["strategy"]
        dry_run = opts["dry_run"]

        cutoff = timezone.now() - timedelta(days=hot_days)

        qs = Taxon.objects.all()

        if strategy == "recent":
            qs = qs.filter(last_accessed_at__gte=cutoff).order_by("-last_accessed_at")
        else:
            qs = qs.order_by("-access_count")

        qs = qs.only("aphia_id", "scientific_name", "cached_at").iterator(chunk_size=200)

        refreshed = 0
        checked = 0
        errors = 0

        for taxon in qs:
            if refreshed >= limit:
                break

            checked += 1
            needs = force or is_stale(taxon)

            if not needs:
                continue

            if dry_run:
                self.stdout.write(f"[DRY] would refresh AphiaID={taxon.aphia_id} {taxon.scientific_name}")
                refreshed += 1
                continue

            try:
                with transaction.atomic():
                    ingest_aphia_id(taxon.aphia_id)
                refreshed += 1
                if refreshed % 50 == 0:
                    self.stdout.write(self.style.SUCCESS(f"Refreshed {refreshed} taxa..."))

            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"Failed AphiaID={taxon.aphia_id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Checked={checked}, Refreshed={refreshed}, Errors={errors}"))
