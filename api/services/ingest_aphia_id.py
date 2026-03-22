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
        self.leafs_dict = {}
        self._record_cache = {}
        self._classification_cache = {}
        self._vernacular_cache = {}
        self._synonym_cache = {}
        self._taxon_cache = {}
        self._processed_vernaculars = set()
        self._processed_taxa = set()

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
        self.leafs_dict = {}
        record = self._record(aphia_id)
        if not record:
            raise ValueError(f"No AphiaRecord for AphiaID={aphia_id}")
        logger.info("Fetched record for AphiaID=%d", aphia_id)
        leaf = self._upsert_taxon_from_record(record)
        self._add_leaf(leaf)
        leaf, aphia_id = self._check_accepted_id(aphia_id, record)
        if leaf:
            self._add_leaf(leaf)

        self._handle_classification_info(aphia_id)
        self._handle_vernaculars_and_synonyms(aphia_id)

        logger.info("Completed ingestion for AphiaID=%d", aphia_id)
        return list(self.leafs_dict.values())

    def _add_leaf(self, taxon: Taxon) -> list[Taxon]:
        """Add a Taxon instance to the leafs_dict and return the list of unique Taxon instances.

        Args:
            taxon: The Taxon instance to add to the leafs_dict

        Returns:
            A list of unique Taxon instances corresponding to the values in the leafs_dict after adding the given taxon
        """
        self.leafs_dict[taxon.aphia_id] = taxon

    def _upsert_taxon_from_record(self, record: dict) -> Taxon:
        """Create or update a Taxon instance based on an AphiaRecord dictionary.

        Args:
            record: A dictionary representing the AphiaRecord, typically obtained from the WoRMS API

        Returns:
            The created or updated Taxon instance corresponding to the AphiaRecord
        """
        aphia_id = int(record["AphiaID"])
        if aphia_id in self._taxon_cache:
            return self._taxon_cache[aphia_id]
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
        self._taxon_cache[aphia_id] = taxon
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
                valid_record = self._record(int(valid_id))
                if valid_record:
                    leaf = self._upsert_taxon_from_record(valid_record)
                aphia_id = int(valid_id)
        return leaf, aphia_id

    def _handle_classification_info(self, aphia_id: int):
        """Fetch and process the classification chain for the given AphiaID, creating/updating Taxon records as needed.

        Args:
            aphia_id: The AphiaID for which to fetch the classification chain

        Returns:
            The updated list of Taxon instances including any new records created/updated for the classification chain
        """
        classification = self._classification(aphia_id)
        if classification:
            chain = self._walk_classification_tree(classification)
            prev_taxon = None
            for node_id, _, _ in chain:
                if node_id in self._processed_taxa:
                    prev_taxon = self.leafs_dict.get(node_id, prev_taxon)
                    continue
                logger.info("Processing classification node AphiaID=%d for root AphiaID=%d", node_id, aphia_id)
                record = self._record(node_id)
                leaf = self._upsert_taxon_from_record(record)
                self._processed_taxa.add(node_id)
                self._add_leaf(leaf)
                if prev_taxon is not None and leaf.parent_id != prev_taxon.aphia_id:
                    leaf.parent = prev_taxon
                    leaf.save(update_fields=["parent"])
                prev_taxon = leaf

        logger.info("Processed classification for AphiaID=%d, now processing vernaculars and synonyms", aphia_id)

    def _handle_vernaculars_and_synonyms(self, aphia_id: int):
        """Fetch and process the vernacular and synonyms for the given AphiaID, creating/updating records as needed.

        Args:
            aphia_id: The AphiaID for which to fetch vernacular names and synonyms
        """
        vernaculars = self._vernaculars(aphia_id)
        seen = set()
        for leaf in self.leafs_dict.values():
            if leaf.aphia_id in self._processed_vernaculars:
                continue
            self._processed_vernaculars.add(leaf.aphia_id)
            Vernacular.objects.filter(taxon=leaf).delete()
            logger.info("Processing vernaculars and synonyms for AphiaID=%d", leaf.aphia_id)
            valid_target = leaf if leaf.status == "accepted" else (leaf.valid_taxon or leaf)
            to_create = []
            for vernacular in vernaculars:
                name = (vernacular.get("vernacular") or "").strip()
                lang = (vernacular.get("language_code") or "").strip()
                if name and lang:
                    to_create.append(Vernacular(taxon=leaf, name=name, language_code=lang))
            if to_create:
                Vernacular.objects.bulk_create(to_create)

            if valid_target.aphia_id in seen:
                continue
            seen.add(valid_target.aphia_id)
            for synonym_record in self._synonyms(valid_target.aphia_id):
                self._upsert_taxon_from_record(synonym_record)

    def _record(self, aphia_id: int) -> dict | None:
        """Fetch the AphiaRecord for a given AphiaID, using a cache to avoid redundant API calls.

        Args:
            aphia_id: The AphiaID for which to fetch the record.

        Returns:
            A dictionary representing the AphiaRecord, or None if not found.
        """
        if aphia_id not in self._record_cache:
            self._record_cache[aphia_id] = self.client.record(aphia_id)
        return self._record_cache[aphia_id]

    def _classification(self, aphia_id: int) -> dict | None:
        """Fetch the classification for a given AphiaID, using a cache to avoid redundant API calls.

        Args:
            aphia_id: The AphiaID for which to fetch the classification.

        Returns:
            A dictionary representing the classification, or None if not found.
        """
        if aphia_id not in self._classification_cache:
            self._classification_cache[aphia_id] = self.client.classification(aphia_id)
        return self._classification_cache[aphia_id]

    def _vernaculars(self, aphia_id: int) -> list[dict]:
        """Fetch the vernacular names for a given AphiaID, using a cache to avoid redundant API calls.

        Args:
            aphia_id: The AphiaID for which to fetch the vernacular names.

        Returns:
            A list of dictionaries representing the vernacular names, or an empty list if not found.
        """
        if aphia_id not in self._vernacular_cache:
            self._vernacular_cache[aphia_id] = self.client.vernaculars(aphia_id) or []
        return self._vernacular_cache[aphia_id]

    def _synonyms(self, aphia_id: int) -> list[dict]:
        """Fetch the synonyms for a given AphiaID, using a cache to avoid redundant API calls.

        Args:
            aphia_id: The AphiaID for which to fetch the synonyms.

        Returns:
            A list of dictionaries representing the synonyms, or an empty list if not found.
        """
        if aphia_id not in self._synonym_cache:
            self._synonym_cache[aphia_id] = self.client.synonyms(aphia_id) or []
        return self._synonym_cache[aphia_id]
