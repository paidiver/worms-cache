"""Base models and enumerations for the API."""

from django.db import models


class DefaultColumns(models.Model):
    """Abstract base model with default columns."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta class for DefaultColumns."""

        abstract = True
