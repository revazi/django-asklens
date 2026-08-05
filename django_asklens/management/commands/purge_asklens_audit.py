"""Preview or execute bounded deletion of built-in database audit rows."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from django_asklens.management._audit_lifecycle import (
    add_lifecycle_arguments,
    canonical_utc,
    capture_purge_high_water,
    ensure_audit_table,
    parse_before,
    purge_in_batches,
    purge_queryset,
    validate_batch_size,
)


class Command(BaseCommand):
    """Permanently delete built-in database audit records."""

    help = (
        "Preview or execute irreversible purging of older AskLens audit rows. "
        "Normal Django delete signals and relationship behavior apply. Earlier "
        "committed batches may remain after a later failure. Test backup/restore "
        "first."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the shared bounded, preview-by-default command contract."""

        add_lifecycle_arguments(
            parser,
            execute_help=(
                "Irreversible deletion of eligible rows; omission performs a "
                "count-only preview."
            ),
        )

    def handle(self, *args: object, **options: object) -> None:
        """Validate, preview, and optionally execute database-only purging."""

        before = parse_before(options["before"])
        alias = ensure_audit_table(options["database"])
        batch_size = validate_batch_size(options["batch_size"])

        try:
            eligible = purge_queryset(alias=alias, before=before).count()
        except DatabaseError:
            raise CommandError(
                "AskLens audit purge could not inspect the selected database."
            ) from None

        self.stdout.write("Operation: purge_asklens_audit")
        self.stdout.write(f"Database alias: {alias}")
        self.stdout.write(f"Cutoff (UTC): {canonical_utc(before)}")
        self.stdout.write(f"Eligible rows (point-in-time): {eligible}")
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write(
            "Warning: Purge is irreversible; normal Django delete signals and "
            "relationship behavior apply."
        )
        self.stdout.write(
            "Warning: Earlier completed batches can remain deleted if a later "
            "batch fails; external signal effects cannot be rolled back."
        )
        self.stdout.write("Warning: Test backup/restore before using --execute.")

        if not options["execute"]:
            self.stdout.write("Mode: PREVIEW")
            self.stdout.write(
                "No rows were deleted. Re-run with --execute to permanently "
                "delete eligible rows."
            )
            return

        try:
            high_water = capture_purge_high_water(alias=alias, before=before)
            deleted_runs = purge_in_batches(
                alias=alias,
                before=before,
                batch_size=batch_size,
                high_water=high_water,
            )
        # Host delete signals and relation policies may raise arbitrary Exceptions.
        except Exception:
            raise CommandError("AskLens audit purge could not be completed.") from None

        self.stdout.write("Mode: EXECUTE")
        self.stdout.write(f"Deleted SemanticQueryRun rows: {deleted_runs}")
