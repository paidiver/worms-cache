"""Service function to ingest an AphiaID and its related data from WoRMS into the local cache DB."""

import logging

from api.models.taxon import Taxon
from api.services.ingest_aphia_id import IngestAphiaId
from api.services.worms_client import WoRMSClient

logger = logging.getLogger(__name__)


class RefreshAphiaId(IngestAphiaId):
    """Class to handle the ingestion of one or more AphiaIDs from WoRMS into the local cache DB."""

    def __init__(self, cutoff: int, dry_run=False):
        """Initialize the RefreshAphiaId instance.

        Args:
            cutoff: The cutoff date for refreshing AphiaIDs.
            dry_run: Whether to only show which AphiaIDs would be refreshed without making changes.
        """
        self.cutoff = cutoff
        self.dry_run = dry_run
        self.client = WoRMSClient()
        aphia_ids = self._get_aphia_ids_to_refresh()
        super().__init__(list(aphia_ids))

    def ingest(self, add_ranks: bool = True):
        """Ingest all AphiaIDs in the set, along with their related data, into the local cache DB.

        Args:
            add_ranks: Whether to also ingest rank information for each taxon (not implemented yet)
        """
        if not self.aphia_ids:
            logger.info("No AphiaIDs to refresh based on the cutoff date")
            return
        if self.dry_run:
            logger.info("Dry run enabled - the following AphiaIDs would be refreshed: %s", sorted(self.aphia_ids))
            return
        super().ingest(add_ranks=add_ranks)

    def _get_aphia_ids_to_refresh(self) -> set[int]:
        """Fetch the set of AphiaIDs that have been updated since the cutoff date.

        Returns:
            A set of AphiaIDs that have been updated since the cutoff date.
        """
        updated_records = self.client.records_by_date(self.cutoff.strftime("%Y-%m-%d"))
        updated_records_id = {record["AphiaID"] for record in updated_records}

        return set(Taxon.objects.filter(aphia_id__in=updated_records_id).values_list("aphia_id", flat=True))
