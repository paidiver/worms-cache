"""Regression coverage for query, dependency, cache, and refresh correctness."""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import NameIndex, RefreshState, Taxon
from api.services.ingest_aphia_id import IngestAphiaId, TaxonNotFound
from api.services.taxamatch_client import TaxamatchError, match_batch
from api.services.worms_client import WoRMSClient, WoRMSError


class QueryAndDependencyTests(APITestCase):
    """Exercise externally observable contracts, including safe errors."""

    def test_invalid_queries_cannot_broaden_or_crash(self):
        """Reject malformed filters and impossible limits before looking up taxa."""
        for params in (
            {"aphia_ids[]": "bad"},
            {"max_matches": "x"},
            {"max_matches": 0},
            {"max_matches": -1},
            {"max_matches": 51},
            {"max_results": "x"},
            {"rank_min": 200, "rank_max": 100},
            {"id_only": "perhaps"},
            {"excluded_ids[]": "bad"},
            {"offset": 0},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/taxa/", params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Content-Type"], "application/problem+json")
                self.assertTrue(response.data["errors"])
        for url in ("/api/taxa/match_names/", "/api/taxa/match_names_pair/"):
            self.assertEqual(self.client.get(url).status_code, 400)

    def test_browse_links_preserve_filters_and_return_arrays(self):
        """Navigate tied names deterministically without changing list bodies."""
        for pk in (3, 1, 2):
            Taxon.objects.create(aphia_id=pk, scientific_name="Cod", rank="Species")
        response = self.client.get("/api/taxa/", {"limit": 2, "rank": "Species"})
        self.assertEqual([item["AphiaID"] for item in response.data], [1, 2])
        self.assertIn("offset=3", response["Link"])
        self.assertIn("rank=Species", response["Link"])
        response = self.client.get("/api/taxa/", {"limit": 2, "offset": 3})
        self.assertEqual([item["AphiaID"] for item in response.data], [3])
        self.assertIn('rel="previous"', response["Link"])
        self.assertNotIn('rel="next"', response["Link"])

    @patch("api.views.taxon._handle_scientific_name_input_and_candidates")
    def test_autocomplete_ranks_then_resolves_then_limits(self, candidates):
        """Several synonyms cannot crowd a distinct accepted taxon out of the limit."""
        accepted = Taxon.objects.create(aphia_id=10, scientific_name="Zulu", rank="Species")
        other = Taxon.objects.create(aphia_id=20, scientific_name="Alpha", rank="Species")
        for pk in (1, 2):
            Taxon.objects.create(aphia_id=pk, scientific_name="Synonym", valid_taxon=accepted)
        candidates.return_value = [2, 1, 20]
        response = self.client.get("/api/taxa/ajax_by_name_part/cod/", {"max_matches": 2})
        self.assertEqual([item["AphiaID"] for item in response.data], [accepted.pk, other.pk])

    @patch("api.views.taxon.candidate_name_rows")
    @patch("api.services.taxamatch_client.requests.post")
    def test_timeout_does_not_become_an_empty_match(self, post, candidates):
        """Both matching operations surface dependency timeouts."""
        candidates.return_value = [SimpleNamespace(id=1, taxon_id=1, name_raw="Cod")]
        post.side_effect = requests.Timeout("private server detail")
        for url, params in (
            ("/api/taxa/match_names/", {"scientificnames[]": "Cod"}),
            ("/api/taxa/ajax_by_name_part/cod/", {}),
        ):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 504)
            self.assertNotIn("private", str(response.data))

    @override_settings(INGEST_API_TOKEN="test")
    @patch("api.views.taxon.IngestAphiaId")
    def test_ingest_missing_dependency_and_internal_errors(self, ingester):
        """Missing taxa, upstream failures, and programming failures remain distinct."""
        for error, expected in ((TaxonNotFound(), 404), (WoRMSError(), 502), (RuntimeError("secret"), 500)):
            ingester.return_value.ingest_aphia_id.side_effect = error
            response = self.client.post("/api/taxa/ingest/", {"aphia_id": 123}, HTTP_AUTHORIZATION="Bearer test")
            self.assertEqual(response.status_code, expected)
            self.assertNotIn("secret", str(response.data))

    @patch("api.services.taxamatch_client.requests.post")
    def test_invalid_batch_responses_are_rejected(self, post):
        """Cardinality, IDs, and per-query errors are part of the upstream contract."""
        query = [{"input": "Cod", "candidates": [{"id": 1, "name": "Cod"}]}]
        for data in (
            {},
            {"results": []},
            {"results": [{"matched_ids": [999]}]},
            {"results": [{"matched_ids": [], "errors": ["failure"]}]},
            {"results": [{"matched_ids": [True]}]},
        ):
            post.return_value = Mock(status_code=200, json=Mock(return_value=data))
            with self.assertRaises(TaxamatchError):
                match_batch(query)

    @patch("api.views.base.requests.get")
    def test_readiness_reports_refresh_and_dependency_failure(self, get):
        """Operational details remain available when matching is down."""
        RefreshState.objects.create(status="failed", failed_ids=[123])
        get.return_value = Mock(status_code=200, json=Mock(return_value={"ok": True}))
        response = self.client.get("/api/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["refresh"]["failed_record_count"], 1)
        get.side_effect = requests.Timeout()
        response = self.client.get("/api/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["dependencies"]["taxamatch"], "unavailable")
        self.assertEqual(self.client.get("/api/health/").status_code, 200)


class CacheIntegrityTests(TestCase):
    """Check persisted relationships and index atomicity using a real database."""

    def make_ingester(self):
        """Provide two taxa sharing one ancestor and a differently ranked synonym."""
        records = {
            pk: {"AphiaID": pk, "scientificname": f"Taxon {pk}", "rank": "Species", "status": "accepted"}
            for pk in (1, 2, 3)
        }
        synonym = {
            "AphiaID": 4,
            "scientificname": "Synonym",
            "rank": "Subspecies",
            "status": "unaccepted",
            "valid_AphiaID": 2,
            "valid_name": "Taxon 2",
        }
        records[4] = synonym
        service = IngestAphiaId({2, 3})
        transaction_depth = len(connection.atomic_blocks)

        def record(pk):
            self.assertEqual(len(connection.atomic_blocks), transaction_depth)
            return records.get(pk)

        service.client = Mock()
        service.client.record.side_effect = record
        service.client.classification.side_effect = lambda pk: {**records[1], "child": records[pk]}
        service.client.vernaculars.return_value = []
        service.client.synonyms.side_effect = lambda pk: {2: [synonym]}.get(pk, [])
        return service

    def test_batch_retains_shared_parent_and_authoritative_rank(self):
        """Sibling ingestion preserves shared ancestry and never copies a synonym rank onto its target."""
        service = self.make_ingester()
        self.assertEqual(service.ingest(add_ranks=False), [])
        self.assertEqual(Taxon.objects.get(pk=2).parent_id, 1)
        self.assertEqual(Taxon.objects.get(pk=3).parent_id, 1)
        self.assertEqual(Taxon.objects.get(pk=2).rank, "Species")
        self.assertTrue(NameIndex.objects.filter(taxon_id=4).exists())

    @patch("api.services.ingest_aphia_id.rebuild_name_index", side_effect=RuntimeError("index failed"))
    def test_index_failure_rolls_back_taxa_and_can_retry(self, rebuild):
        """A failed index update leaves neither partial taxa nor stale in-memory state."""
        service = self.make_ingester()
        with self.assertRaises(RuntimeError):
            service.ingest_aphia_id(2)
        self.assertFalse(Taxon.objects.exists())
        rebuild.side_effect = None
        service.ingest_aphia_id(2)
        self.assertEqual(Taxon.objects.get(pk=2).parent_id, 1)

    def test_tree_cycles_terminate(self):
        """A corrupt cycle cannot recurse indefinitely or include the starting taxon."""
        root = Taxon.objects.create(aphia_id=1, scientific_name="Root")
        child = Taxon.objects.create(aphia_id=2, scientific_name="Child", parent=root)
        root.parent = child
        root.save()
        self.assertEqual([taxon.pk for taxon in root.descendants], [2])
        self.assertEqual([taxon.pk for taxon in root.parents], [2])


class RefreshReliabilityTests(TestCase):
    """Verify pagination, durable checkpoints, and failure retries."""

    @patch.object(WoRMSClient, "_get")
    def test_all_change_pages_are_fetched_in_a_fixed_window(self, get):
        """Changes after the first upstream page are retained with explicit filters."""
        get.side_effect = [[{"AphiaID": pk} for pk in range(1, 51)], [{"AphiaID": 51}]]
        records = WoRMSClient().records_by_date("2026-01-01", "2026-01-02")
        self.assertEqual(len(records), 51)
        params = [parse_qs(urlsplit(call.args[0]).query) for call in get.call_args_list]
        self.assertEqual([item["offset"] for item in params], [["1"], ["51"]])
        self.assertTrue(all(item["enddate"] == ["2026-01-02"] and item["marine_only"] == ["false"] for item in params))

    @patch("api.management.commands.refresh_worms.rebuild_name_index")
    @patch("api.management.commands.refresh_worms.RefreshAphiaId")
    def test_failed_refresh_retains_checkpoint_and_next_run_retries(self, refresh, rebuild):
        """Even a long gap resumes from the last success, advancing only after a successful run."""
        original = timezone.now() - timedelta(days=30)
        state = RefreshState.objects.create(last_success_at=original)
        refresh.return_value.ingest.return_value = [123]
        with self.assertRaises(CommandError):
            call_command("refresh_worms", stdout=StringIO())
        state.refresh_from_db()
        self.assertEqual(state.last_success_at, original)
        self.assertEqual(state.failed_ids, [123])
        rebuild.assert_not_called()
        refresh.return_value.ingest.return_value = []
        call_command("refresh_worms", stdout=StringIO())
        self.assertEqual(refresh.call_args.args[0], original - timedelta(days=1))
        state.refresh_from_db()
        self.assertGreater(state.last_success_at, original)
        self.assertEqual(state.status, "ok")
        self.assertEqual(state.failed_ids, [])

    @patch("api.management.commands.refresh_worms.RefreshAphiaId")
    def test_dry_run_does_not_create_progress(self, refresh):
        """A preview never starts or advances a refresh checkpoint."""
        call_command("refresh_worms", dry_run=True)
        self.assertFalse(RefreshState.objects.exists())
        self.assertTrue(refresh.call_args.kwargs["dry_run"])
