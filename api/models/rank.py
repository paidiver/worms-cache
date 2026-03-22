"""Models for vernacular names in the WoRMS cache API."""

from django.db import models

from api.models.base import DefaultColumns


class Rank(DefaultColumns):
    """Model representing a rank for a taxon."""

    name = models.CharField(primary_key=True, max_length=64, db_index=True)
    rank_id = models.PositiveIntegerField()

    class Meta:
        """Meta information for the Rank model."""

        db_table = "ranks"
        constraints = [models.UniqueConstraint(fields=["rank_id", "name"], name="uq_rank")]
        indexes = [
            models.Index(fields=["rank_id"], name="rank_id_idx"),
            models.Index(fields=["name"], name="rank_name_idx"),
        ]
