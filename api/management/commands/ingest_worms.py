"""Management command to ingest AphiaIDs from WoRMS into the local cache DB."""

from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from api.services.ingest_aphia_id import IngestAphiaId
from api.services.rebuild_name_index import rebuild_name_index


class Command(BaseCommand):
    """Django management command to ingest one or more AphiaIDs from WoRMS into the local cache DB."""

    help = "Ingest one or more AphiaIDs from WoRMS into the local cache DB."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command-line arguments.

        Args:
            parser: The argument parser to which command-line arguments can be added.
        """
        parser.add_argument("--ids", nargs="*", type=int)
        parser.add_argument("--file", type=str)
        parser.add_argument("--add-ranks", action="store_true")

    def handle(self, *args, **opts):
        """Handle the command execution.

        Args:
            *args: Positional arguments (not used).
            **opts: Command-line options, including "ids" which is a list of AphiaIDs to ingest.
        """
        ids = set(opts.get("ids") or [])
        if opts.get("file"):
            with open(opts["file"]) as f:
                ids.update(int(line.strip()) for line in f if line.strip())

        ingest_aphiad_id = IngestAphiaId(ids)
        ingest_aphiad_id.ingest(add_ranks=opts.get("add_ranks", False))
        rebuild_name_index()
