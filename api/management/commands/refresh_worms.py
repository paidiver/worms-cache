"""Refresh every upstream change page with a durable success checkpoint."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from api.models import RefreshState
from api.services.rebuild_name_index import rebuild_name_index
from api.services.refresh_aphia_id import RefreshAphiaId

REFRESH_LOCK_ID = 871402


class Command(BaseCommand):
    """Refresh cached taxa without skipping failed or missed windows."""

    help = "Refresh WoRMS changes since the last success (initial lookback: --cache-ttl days)."

    def add_arguments(self, parser):
        """Configure the initial lookback and read-only preview."""
        parser.add_argument("--cache-ttl", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        """Serialize refresh runs using a session-level PostgreSQL advisory lock."""
        if opts["cache_ttl"] < 1:
            raise CommandError("--cache-ttl must be a positive number of days.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [REFRESH_LOCK_ID])
            if not cursor.fetchone()[0]:
                raise CommandError("A WoRMS refresh is already running.")
        try:
            self._refresh(opts)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [REFRESH_LOCK_ID])

    def _refresh(self, opts):
        """Advance progress only after ingestion and index rebuilding succeed."""
        end_date = timezone.now()
        state = RefreshState.objects.filter(pk="worms").first()
        cutoff = (
            state.last_success_at - timedelta(days=1)
            if state and state.last_success_at
            else end_date - timedelta(days=opts["cache_ttl"])
        )
        if opts["dry_run"]:
            RefreshAphiaId(cutoff, dry_run=True, end_date=end_date).ingest()
            return
        state, _ = RefreshState.objects.get_or_create(pk="worms")
        state.started_at, state.finished_at, state.status, state.failed_ids = end_date, None, "running", []
        state.save()
        try:
            failures = RefreshAphiaId(cutoff, end_date=end_date).ingest() or []
            state.failed_ids = failures
            if failures:
                raise CommandError(f"Failed to refresh {len(failures)} AphiaIDs; checkpoint unchanged.")
            rebuild_name_index()
        except Exception as exc:
            state.status = "failed"
            state.finished_at = timezone.now()
            state.save()
            raise CommandError("WoRMS refresh failed; the next run will retry this window.") from exc
        state.last_success_at, state.status, state.finished_at = end_date, "ok", timezone.now()
        state.save()
        self.stdout.write(self.style.SUCCESS("WoRMS refresh completed."))
