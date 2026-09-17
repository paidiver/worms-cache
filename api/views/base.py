"""API views module."""

import requests
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import RefreshState


@extend_schema(tags=["Health Check"])
class HealthView(APIView):
    """Health check view to verify service status."""

    @extend_schema(
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}},
    )
    def get(self, request):
        """Health check endpoint.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response indicating service status
        """
        return Response({"status": "ok"})


@extend_schema(tags=["Health Check"])
class ReadinessView(APIView):
    """Report database and matching availability without querying the public WoRMS API."""

    @extend_schema(responses={200: {"type": "object"}, 503: {"type": "object"}})
    def get(self, request):
        """Check dependencies with bounded timeouts and expose refresh progress."""
        dependencies = {"database": "ok", "taxamatch": "ok"}
        refresh = None
        try:
            state = RefreshState.objects.filter(pk="worms").first()
            refresh = {
                "status": state.status if state else "never_run",
                "last_success_at": state.last_success_at if state else None,
                "started_at": state.started_at if state else None,
                "finished_at": state.finished_at if state else None,
                "failed_record_count": len(state.failed_ids) if state else 0,
                "age_seconds": (timezone.now() - state.last_success_at).total_seconds()
                if state and state.last_success_at
                else None,
            }
        except DatabaseError:
            dependencies["database"] = "unavailable"
        try:
            response = requests.get(f"{settings.TAXAMATCH_URL}/health", timeout=2)
            if response.status_code != status.HTTP_200_OK or response.json().get("ok") is not True:
                dependencies["taxamatch"] = "unavailable"
        except (requests.RequestException, ValueError, AttributeError):
            dependencies["taxamatch"] = "unavailable"
        ready = all(value == "ok" for value in dependencies.values())
        data = {"status": "ok" if ready else "unavailable", "dependencies": dependencies, "refresh": refresh}
        if ready:
            return Response(data)
        # Operational fields are extensions of the standard error format.
        return Response(
            {
                "type": "about:blank",
                "title": "Service Unavailable",
                "status": 503,
                "detail": "One or more cache dependencies are unavailable.",
                "code": "dependency_unavailable",
                "dependencies": dependencies,
                "refresh": refresh,
            },
            status=503,
        )
