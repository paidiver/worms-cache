"""API views module."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView


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
