"""Durable refresh progress and operational status."""

from django.db import models


class RefreshState(models.Model):
    """A single checkpoint advanced only after a complete successful refresh."""

    name = models.CharField(max_length=32, primary_key=True, default="worms")
    last_success_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, default="never_run")
    failed_ids = models.JSONField(default=list)
