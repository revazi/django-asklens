"""Preview or execute bounded redaction of built-in database audit rows."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from django_asklens.management._audit_lifecycle import (
    add_lifecycle_arguments,
    canonical_utc,
    ensure_audit_table,
    parse_before,
    redact_in_batches,
    redaction_queryset,
    validate_batch_size,
)


class Command(BaseCommand):
    """Redact sensitive content from built-in database audit records."""

    help = "Preview or redact question and plan content in AskLens database audits."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the bounded, preview-by-default command contract."""

        add_lifecycle_arguments(
            parser,
            execute_help=("Apply redaction; omission performs a count-only preview."),
        )

    def handle(self, *args: object, **options: object) -> None:
        """Validate, preview, and optionally execute database-only redaction."""

        before = parse_before(options["before"])
        alias = ensure_audit_table(options["database"])
        batch_size = validate_batch_size(options["batch_size"])

        try:
            eligible = redaction_queryset(alias=alias, before=before).count()
        except DatabaseError:
            raise CommandError(
                "AskLens audit redaction could not inspect the selected database."
            ) from None

        self.stdout.write("Operation: redact_asklens_audit")
        self.stdout.write(f"Database alias: {alias}")
        self.stdout.write(f"Cutoff (UTC): {canonical_utc(before)}")
        self.stdout.write(f"Eligible rows (point-in-time): {eligible}")
        self.stdout.write(f"Batch size: {batch_size}")

        if not options["execute"]:
            self.stdout.write("Mode: PREVIEW")
            self.stdout.write(
                "No rows were modified. Re-run with --execute to redact eligible rows."
            )
            return

        try:
            redacted = redact_in_batches(
                alias=alias,
                before=before,
                batch_size=batch_size,
            )
        except DatabaseError:
            raise CommandError(
                "AskLens audit redaction could not update the selected database."
            ) from None

        self.stdout.write("Mode: EXECUTE")
        self.stdout.write(f"Redacted rows: {redacted}")
