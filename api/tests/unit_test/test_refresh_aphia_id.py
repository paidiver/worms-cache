"""Unit tests for RefreshAphiaId service."""

import datetime as dt
from unittest.mock import MagicMock, patch

from django.test import TestCase

from api.models.taxon import Taxon
from api.services.refresh_aphia_id import RefreshAphiaId


class RefreshAphiaIdTests(TestCase):
    """Tests for RefreshAphiaId."""

    def setUp(self):
        """Set up test data for RefreshAphiaId tests."""
        self.taxon1 = Taxon.objects.create(
            aphia_id=101,
            scientific_name="Animalia",
            rank="Kingdom",
            status="accepted",
        )
        self.taxon2 = Taxon.objects.create(
            aphia_id=202,
            scientific_name="Gadus morhua",
            rank="Species",
            status="accepted",
        )

    @patch("api.services.refresh_aphia_id.IngestAphiaId.__init__", return_value=None)
    @patch("api.services.refresh_aphia_id.WoRMSClient")
    def test_init_builds_aphia_ids_from_records_and_existing_taxa(
        self,
        MockClient: MagicMock,
        mock_super_init: MagicMock,
    ):
        """Test that RefreshAphiaId.__init__() builds the set of AphiaIDs to refresh based on records from WoRMS.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
            mock_super_init: The mocked IngestAphiaId.__init__ method, injected by the @patch decorator.
        """
        client = MockClient.return_value
        client.records_by_date.return_value = [
            {"AphiaID": 101},
            {"AphiaID": 202},
            {"AphiaID": 303},
        ]

        cutoff = dt.date(2026, 1, 1)

        RefreshAphiaId(cutoff=cutoff, dry_run=False)

        client.records_by_date.assert_called_once_with("2026-01-01")

        mock_super_init.assert_called_once()
        passed_ids = mock_super_init.call_args[0][0]

        self.assertCountEqual(passed_ids, [101, 202])

    @patch("api.services.refresh_aphia_id.logger")
    @patch("api.services.refresh_aphia_id.IngestAphiaId.ingest")
    def test_ingest_no_aphia_ids_logs_and_returns(self, mock_super_ingest: MagicMock, mock_logger: MagicMock):
        """If there are no aphia_ids to refresh, ingest() should log and return without calling super().ingest.

        Args:
            mock_super_ingest: The mocked IngestAphiaId.ingest method.
            mock_logger: The mocked logger.
        """
        svc = RefreshAphiaId.__new__(RefreshAphiaId)
        svc.aphia_ids = set()
        svc.dry_run = False

        svc.ingest(add_ranks=True)

        mock_logger.info.assert_called_once()
        mock_super_ingest.assert_not_called()

    @patch("api.services.refresh_aphia_id.logger")
    @patch("api.services.refresh_aphia_id.IngestAphiaId.ingest")
    def test_ingest_dry_run_logs_and_returns(self, mock_super_ingest: MagicMock, mock_logger: MagicMock):
        """If dry_run=True, ingest() should log which AphiaIDs would be refreshed and return without super().ingest.

        Args:
            mock_super_ingest: The mocked IngestAphiaId.ingest method.
            mock_logger: The mocked logger.
        """
        svc = RefreshAphiaId.__new__(RefreshAphiaId)
        svc.aphia_ids = {202, 101}
        svc.dry_run = True

        svc.ingest(add_ranks=False)

        mock_logger.info.assert_called_once()
        mock_super_ingest.assert_not_called()

    @patch("api.services.refresh_aphia_id.IngestAphiaId.ingest")
    def test_ingest_calls_super_when_not_dry_run(self, mock_super_ingest: MagicMock):
        """If dry_run=False and there are aphia_ids, ingest() should call super().ingest(add_ranks=...).

        Args:
            mock_super_ingest: The mocked IngestAphiaId.ingest method.
        """
        svc = RefreshAphiaId.__new__(RefreshAphiaId)
        svc.aphia_ids = {101}
        svc.dry_run = False

        svc.ingest(add_ranks=True)

        mock_super_ingest.assert_called_once_with(add_ranks=True)
