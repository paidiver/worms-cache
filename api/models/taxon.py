"""Models for taxa in the WoRMS cache API."""

from django.db import models

from .base import DefaultColumns


class Taxon(DefaultColumns):
    """Model representing a taxon in the WoRMS cache."""

    aphia_id = models.PositiveIntegerField(primary_key=True)
    scientific_name = models.CharField(max_length=512, db_index=True)
    rank = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=64, db_index=True)
    valid_taxon = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="synonym_children",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    worms_modified = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)

    cached_at = models.DateTimeField(auto_now=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    access_count = models.BigIntegerField(default=0)

    @property
    def descendants(self) -> list["Taxon"]:
        """Get all descendant taxa recursively in traversal order."""
        descendants = []

        def _get_descendants(taxon):
            children = list(taxon.children.all().order_by("scientific_name"))
            for child in children:
                descendants.append(child)
                _get_descendants(child)

        _get_descendants(self)
        return descendants

    @property
    def parents(self) -> list["Taxon"]:
        """Get all parent taxa from root to immediate parent."""
        parents = []
        current_taxon = self.parent
        while current_taxon:
            parents.append(current_taxon)
            current_taxon = current_taxon.parent
        return parents[::-1]

    @property
    def synonyms(self):
        """Return a queryset of Taxon instances that are synonyms of this taxon."""
        return self.synonym_children.exclude(aphia_id=self.aphia_id)

    class Meta:
        """Meta information for the Taxon model."""

        db_table = "taxa"
        indexes = [
            models.Index(fields=["rank", "status"], name="taxa_rank_status_idx"),
            models.Index(fields=["scientific_name"], name="taxa_scientific_name_idx"),
            models.Index(fields=["parent"], name="taxa_parent_idx"),
            models.Index(fields=["valid_taxon"], name="taxa_valid_taxon_idx"),
            models.Index(fields=["cached_at"], name="taxa_cached_at_idx"),
        ]
