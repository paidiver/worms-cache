"""Service function to ingest an AphiaID and its related data from WoRMS into the local cache DB."""

import logging

from django.db import transaction
from django.utils.dateparse import parse_datetime

from api.models import Taxon, Vernacular
from api.models.rank import Rank

from .worms_client import WoRMSClient

logger = logging.getLogger(__name__)


class IngestAphiaId:
    """Class to handle the ingestion of one or more AphiaIDs from WoRMS into the local cache DB."""

    def __init__(self, aphia_ids: set[int]):
        """Initialize the IngestAphiaId instance.

        Args:
            aphia_ids: A set of AphiaIDs to ingest
        """
        self.aphia_ids = aphia_ids
        self.client = WoRMSClient()

    def ingest(self, add_ranks: bool = True):
        """Ingest all AphiaIDs in the set, along with their related data, into the local cache DB.

        Args:
            add_ranks: Whether to also ingest rank information for each taxon (not implemented yet)
        """
        if add_ranks:
            self.ingest_ranks()
        for aphia_id in sorted(self.aphia_ids):
            try:
                self.ingest_aphia_id(aphia_id)
            except Exception as e:
                logger.error("Error ingesting AphiaID=%d: %s", aphia_id, str(e))

    @transaction.atomic
    def ingest_ranks(self):
        """Ingest rank information for all AphiaIDs in the set, skipping duplicates from the client."""
        ranks = self.client.ranks()
        if not ranks:
            raise ValueError("No rank information found")

        logger.info("Fetched rank information")

        seen: set[tuple[int, str]] = set()

        for rank in ranks:
            taxon_rank_id = int(rank["taxonRankID"])

            name = (rank.get("taxonRank") or "").strip()

            key = (taxon_rank_id, name)

            if key in seen:
                continue
            seen.add(key)

            self._upsert_rank(rank)
            logger.info("Ingested rank information for taxonRankID=%d", taxon_rank_id)

        logger.info(
            "Completed ingestion of rank information: %d unique ranks ingested",
            len(seen),
        )

    @transaction.atomic
    def ingest_aphia_id(self, aphia_id: int) -> list[Taxon]:
        """Ingest an AphiaID and its related data from WoRMS into the local cache DB.

        Args:
            aphia_id: The AphiaID to ingest

        Returns:
            A list of Taxon instances corresponding to the ingested AphiaID and its related data, after
        creating/updating the record, classification chain, vernacular names, and synonyms in the local cache DB.
        """
        logger.info("Starting ingestion for AphiaID=%d", aphia_id)
        record = self.client.record(aphia_id)
        if not record:
            raise ValueError(f"No AphiaRecord for AphiaID={aphia_id}")
        logger.info("Fetched record for AphiaID=%d", aphia_id)
        leafs = []
        leaf = self._upsert_taxon_from_record(record)
        leafs.append(leaf)
        leaf, aphia_id = self._check_accepted_id(aphia_id, record)
        if leaf and leaf not in leafs:
            leafs.append(leaf)

        leafs = self._handle_classification_info(aphia_id, leafs)
        leafs = self._handle_vernaculars_and_synonyms(aphia_id, leafs)

        logger.info("Completed ingestion for AphiaID=%d", aphia_id)
        return leafs

    def _upsert_taxon_from_record(self, record: dict) -> Taxon:
        """Create or update a Taxon instance based on an AphiaRecord dictionary.

        Args:
            record: A dictionary representing the AphiaRecord, typically obtained from the WoRMS API

        Returns:
            The created or updated Taxon instance corresponding to the AphiaRecord
        """
        aphia_id = int(record["AphiaID"])
        valid_id = record.get("valid_AphiaID")
        status = record.get("status") or ""
        valid_taxon = None
        if valid_id and int(valid_id) != aphia_id:
            valid_taxon, _ = Taxon.objects.update_or_create(
                aphia_id=int(valid_id),
                defaults={
                    "scientific_name": record.get("valid_name") or "",
                    "rank": record.get("rank") or "",
                    "status": "accepted",
                },
            )

        worms_modified = record.get("modified")
        worms_modified_dt = parse_datetime(worms_modified) if worms_modified else None

        taxon, _ = Taxon.objects.update_or_create(
            aphia_id=aphia_id,
            defaults={
                "scientific_name": record.get("scientificname") or "",
                "rank": record.get("rank") or "",
                "status": status,
                "valid_taxon": valid_taxon,
                "worms_modified": worms_modified_dt,
                "source_url": record.get("url"),
            },
        )
        return taxon

    def _upsert_rank(self, rank_record: dict):
        """Create or update a Rank instance based on a rank record dictionary.

        Args:
            rank_record: A dictionary representing the rank information, typically obtained from the WoRMS API
        """
        name = rank_record.get("taxonRank")
        rank_id = rank_record.get("taxonRankID")
        Rank.objects.update_or_create(
            rank_id=int(rank_id),
            name=name.strip() if name else "",
        )

    def _walk_classification_tree(self, tree: dict) -> list[tuple[int, str, str]]:
        """Returns a root->leaf chain for the /AphiaClassificationByAphiaID/{id} nested structure.

        Args:
            tree: A nested dictionary representing the classification chain, typically obtained from the WoRMS API

        Returns:
            A list of tuples containing the AphiaID, rank, and scientific name for each taxon in classification chain.
        """
        chain = []
        current = tree
        while current is not None:
            chain.append((int(current["AphiaID"]), current.get("rank") or "", current.get("scientificname") or ""))
            current = current.get("child")
        return chain

    def _check_accepted_id(self, aphia_id: int, record: dict) -> tuple[Taxon | None, int]:
        """Check if the given AphiaID is unaccepted and return the valid taxon and its AphiaID if so.

        Args:
            aphia_id: The original AphiaID to check
            record: The AphiaRecord dictionary corresponding to the original AphiaID

        Returns:
            A tuple containing the Taxon instance corresponding to the valid taxon (or original taxon if accepted) and
        the AphiaID of the valid taxon (or original AphiaID if accepted)
        """
        leaf = None
        if record["status"] == "unaccepted":
            logger.info(
                "AphiaID=%d is unaccepted, also ingesting valid taxon AphiaID=%s", aphia_id, record.get("valid_AphiaID")
            )
            valid_id = record.get("valid_AphiaID")
            if valid_id:
                valid_record = self.client.record(int(valid_id))
                if valid_record:
                    leaf = self._upsert_taxon_from_record(valid_record)
                aphia_id = int(valid_id)
        return leaf, aphia_id

    def _handle_classification_info(self, aphia_id: int, leafs: list[Taxon]) -> list[Taxon]:
        """Fetch and process the classification chain for the given AphiaID, creating/updating Taxon records as needed.

        Args:
            aphia_id: The AphiaID for which to fetch the classification chain
            leafs: The list of Taxon instances already created/updated for the original AphiaID and its valid taxon

        Returns:
            The updated list of Taxon instances including any new records created/updated for the classification chain
        """
        classification = self.client.classification(aphia_id)
        if classification:
            chain = self._walk_classification_tree(classification)
            prev_taxon = None
            for node_id, _, _ in chain:
                logger.info("Processing classification node AphiaID=%d for root AphiaID=%d", node_id, aphia_id)
                record = self.client.record(node_id)
                leaf = self._upsert_taxon_from_record(record)
                leafs.append(leaf)
                if prev_taxon is not None and leaf.parent_id != prev_taxon.aphia_id:
                    leaf.parent = prev_taxon
                    leaf.save(update_fields=["parent"])
                prev_taxon = leaf

        logger.info("Processed classification for AphiaID=%d, now processing vernaculars and synonyms", aphia_id)
        return leafs

    def _handle_vernaculars_and_synonyms(self, aphia_id: int, leafs: list[Taxon]) -> list[Taxon]:
        """Fetch and process the vernacular and synonyms for the given AphiaID, creating/updating records as needed.

        Args:
            aphia_id: The AphiaID for which to fetch vernacular names and synonyms
            leafs: The list of Taxon instances already created/updated for the original AphiaID and its
        classification chain

        Returns:
            The updated list of Taxon instances including any new records created/updated for vernacular names and
        synonyms
        """
        for leaf in leafs:
            logger.info("Processing vernaculars and synonyms for AphiaID=%d", leaf.aphia_id)
            Vernacular.objects.filter(taxon=leaf).delete()
            for vernacular in self.client.vernaculars(aphia_id):
                name = (vernacular.get("vernacular") or "").strip()
                lang = (vernacular.get("language_code") or "").strip()
                if name and lang:
                    Vernacular.objects.create(taxon=leaf, name=name, language_code=lang)

            valid_target = leaf if leaf.status == "accepted" else (leaf.valid_taxon or leaf)

            for synonym_record in self.client.synonyms(valid_target.aphia_id):
                self._upsert_taxon_from_record(synonym_record)
        return leafs
