"""apps.py module."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API application configuration class."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """Import signal handlers."""
        import api.schema  # noqa: F401
