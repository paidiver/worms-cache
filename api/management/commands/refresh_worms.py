"""Django management command to refresh cached WoRMS taxa based on specified cache TTL."""

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.services.rebuild_name_index import rebuild_name_index
from api.services.refresh_aphia_id import RefreshAphiaId


class Command(BaseCommand):
    """Django management command to refresh cached WoRMS taxa based on specified cache TTL."""

    help = "Refresh cached WoRMS taxa based on specified cache TTL."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command-line arguments.

        Args:
            parser: The argument parser to which command-line arguments can be added.
        """
        parser.add_argument(
            "--cache-ttl", type=int, default=7, help="Compare with the last updated time in the WoRMS main api"
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
        cache_ttl = opts["cache_ttl"]
        dry_run = opts["dry_run"]
        cutoff = timezone.now() - timedelta(days=cache_ttl)

        refresh_aphiad_id = RefreshAphiaId(cutoff, dry_run)
        refresh_aphiad_id.ingest(add_ranks=True)
        if not dry_run:
            rebuild_name_index()
