"""Unit tests for the Taxamatch client (match_batch)."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api.services.taxamatch_client import TaxamatchError, match_batch


class TaxamatchClientTests(SimpleTestCase):
    """Tests for match_batch()."""

    @patch("api.services.taxamatch_client.settings")
    @patch("api.services.taxamatch_client.requests.post")
    def test_match_batch_success_returns_results(self, mock_post: MagicMock, mock_settings: MagicMock):
        """Test that match_batch() returns the expected results on a successful response from the Taxamatch service.

        Args:
            mock_post: The mocked requests.post function, injected by the @patch decorator.
            mock_settings: The mocked settings object, injected by the @patch decorator.
        """
        mock_settings.TAXAMATCH_URL = "https://taxamatch.example"

        queries = [
            {"q": "gadus morhua", "candidates": [{"id": 1, "name": "Gadus morhua"}]},
            {"q": "homo sapiens", "candidates": [{"id": 2, "name": "Homo sapiens"}]},
        ]

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {"q": "gadus morhua", "matched_ids": [1], "errors": []},
                {"q": "homo sapiens", "matched_ids": [], "errors": []},
            ]
        }
        mock_post.return_value = resp

        out = match_batch(queries, timeout=5.5)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["matched_ids"], [1])
        self.assertEqual(out[1]["matched_ids"], [])

        mock_post.assert_called_once()
        called_url = (
            mock_post.call_args.kwargs["url"] if "url" in mock_post.call_args.kwargs else mock_post.call_args.args[0]
        )
        self.assertEqual(called_url, "https://taxamatch.example/match")
        self.assertEqual(mock_post.call_args.kwargs["json"], {"queries": queries})
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 5.5)

    @patch("api.services.taxamatch_client.settings")
    @patch("api.services.taxamatch_client.requests.post")
    def test_match_batch_success_missing_results_returns_empty_list(
        self, mock_post: MagicMock, mock_settings: MagicMock
    ):
        """Test that match_batch() returns an empty list if the response from the Taxamatch service is successful.

        But missing the 'results' key.

        Args:
            mock_post: The mocked requests.post function, injected by the @patch decorator.
            mock_settings: The mocked settings object, injected by the @patch decorator.
        """
        mock_settings.TAXAMATCH_URL = "https://taxamatch.example"

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"something_else": []}
        mock_post.return_value = resp

        out = match_batch([{"q": "x", "candidates": []}])
        self.assertEqual(out, [])

    @patch("api.services.taxamatch_client.settings")
    @patch("api.services.taxamatch_client.requests.post")
    def test_match_batch_non_200_raises_taxamatch_error(self, mock_post: MagicMock, mock_settings: MagicMock):
        """Test that match_batch() raises a TaxamatchError if the response from the Taxamatch service has a non-200.

        Args:
            mock_post: The mocked requests.post function, injected by the @patch decorator.
            mock_settings: The mocked settings object, injected by the @patch decorator.
        """
        mock_settings.TAXAMATCH_URL = "https://taxamatch.example"

        resp = MagicMock()
        resp.status_code = 500
        resp.text = "X" * 2000
        mock_post.return_value = resp

        with self.assertRaises(TaxamatchError) as ctx:
            match_batch([{"q": "gadus morhua", "candidates": []}], timeout=1.0)

        msg = str(ctx.exception)
        self.assertIn("Taxamatch service error 500", msg)
        self.assertLessEqual(len(msg), len("Taxamatch service error 500: ") + 500)

    @patch("api.services.taxamatch_client.settings")
    @patch("api.services.taxamatch_client.requests.post")
    def test_match_batch_uses_default_timeout(self, mock_post: MagicMock, mock_settings: MagicMock):
        """Test that match_batch() uses the default timeout of 3.0 seconds if no timeout is provided.

        Args:
            mock_post: The mocked requests.post function, injected by the @patch decorator.
            mock_settings: The mocked settings object, injected by the @patch decorator.
        """
        mock_settings.TAXAMATCH_URL = "https://taxamatch.example"

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"results": []}
        mock_post.return_value = resp

        match_batch([{"q": "a", "candidates": []}])
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 3.0)
