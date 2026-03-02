"""Tests for base API functionality."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthTests(APITestCase):
    """Integration tests for LabelViewSet endpoints."""

    def test_health_endpoint(self):
        """Test the health endpoint."""
        resp = self.client.get(reverse("Health"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"status": "ok"})
