"""apps.py module."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API application configuration class."""

    name = "api"

    def ready(self):
        """Import signal handlers."""
        import api.schema  # noqa: F401
