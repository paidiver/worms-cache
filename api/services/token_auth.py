"""Custom authentication class that checks for a token in the Authorization header."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import authentication, exceptions
from rest_framework.request import Request


class TokenAuth(authentication.BaseAuthentication):
    """Custom authentication class that checks for a token in the Authorization header."""

    def authenticate(self, request: Request) -> tuple[type[models.Model], None] | None:
        """Authenticate the request by checking for a token in the Authorization header.

        Args:
            request: The incoming HTTP request to authenticate.

        Raises:
            AuthenticationFailed: If a token is provided but is invalid.

        Returns:
            A tuple of (user, None) if authentication is successful, or None if no token is provided.
        """
        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "

        if not auth_header.startswith(prefix):
            return None

        token = auth_header[len(prefix) :].strip()
        expected = getattr(settings, "INGEST_API_TOKEN", None)

        if not expected or token != expected:
            raise exceptions.AuthenticationFailed("Invalid service token.")

        User = get_user_model()
        service_user, _ = User.objects.get_or_create(
            username="service-ingest",
            defaults={"is_staff": False, "is_superuser": False},
        )
        return (service_user, None)
