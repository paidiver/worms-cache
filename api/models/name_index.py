"""Defines the NameIndex model, which stores search-optimized name strings for taxa.

Including accepted names and synonyms. This model is used to facilitate efficient searching and indexing of
taxon names in the WoRMS cache API.
"""

from django.contrib.postgres.indexes import GinIndex
from django.db import models

from api.models.taxon import Taxon


class NameType(models.TextChoices):
    """Enum for the type of name index entry, either accepted name or synonym."""

    ACCEPTED = "accepted", "Accepted"
    SYNONYM = "synonym", "Synonym"


class NameIndex(models.Model):
    """Search-optimized name strings for taxa (includes accepted names and synonyms)."""

    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="name_index")
    name_type = models.CharField(max_length=16, choices=NameType.choices)
    name_raw = models.CharField(max_length=512)

    canonical_norm = models.CharField(max_length=512, db_index=True)
    genus_norm = models.CharField(max_length=128, db_index=True, null=True, blank=True)
    epithet_norm = models.CharField(max_length=128, db_index=True, null=True, blank=True)

    genus_prefix2 = models.CharField(max_length=2, db_index=True, null=True, blank=True)
    genus_prefix3 = models.CharField(max_length=3, db_index=True, null=True, blank=True)
    canon_prefix3 = models.CharField(max_length=3, db_index=True, null=True, blank=True)

    class Meta:
        """Meta information for the NameIndex model."""

        db_table = "name_index"
        constraints = [models.UniqueConstraint(fields=["taxon", "name_type", "name_raw"], name="uq_nameindex")]
        indexes = [
            models.Index(fields=["genus_norm", "epithet_norm"], name="nameidx_genus_epithet_idx"),
            GinIndex(
                name="nameidx_canon_trgm_gin",
                fields=["canonical_norm"],
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                name="nameidx_genus_trgm_gin",
                fields=["genus_norm"],
                opclasses=["gin_trgm_ops"],
            ),
        ]
