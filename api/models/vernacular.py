"""Models for vernacular names in the WoRMS cache API."""

from django.contrib.postgres.indexes import GinIndex
from django.db import models

from api.models.base import DefaultColumns
from api.models.taxon import Taxon


class Vernacular(DefaultColumns):
    """Model representing a vernacular name for a taxon."""

    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="vernaculars")
    name = models.CharField(max_length=512)
    language_code = models.CharField(max_length=8, db_index=True)

    class Meta:
        """Meta information for the Vernacular model."""

        db_table = "vernaculars"
        constraints = [models.UniqueConstraint(fields=["taxon", "name", "language_code"], name="uq_vern")]
        indexes = [
            models.Index(fields=["taxon"], name="vern_taxon_idx"),
            models.Index(fields=["taxon", "language_code"], name="vern_taxon_lang_idx"),
            GinIndex(
                name="vern_name_trgm_gin",
                fields=["name"],
                opclasses=["gin_trgm_ops"],
            ),
        ]
