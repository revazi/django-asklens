"""Report a privacy-safe summary of the process-local AskLens registry."""

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_asklens.catalog.registry import default_registry


class Command(BaseCommand):
    """Check whether AskLens resources were registered during Django startup."""

    help = (
        "Report aggregate counts for the process-local AskLens registry without "
        "querying application data or invoking scope providers."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the optional empty-registry failure mode."""

        parser.add_argument(
            "--fail-on-empty",
            action="store_true",
            help="Exit nonzero when no AskLens resources are registered.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Print aggregate in-memory metadata and optionally reject emptiness."""

        resources = default_registry.all()
        resource_count = len(resources)
        global_count = sum(item.scope_mode == "global" for item in resources)
        scoped_count = sum(item.scope_mode == "context_scoped" for item in resources)
        field_count = sum(len(item.fields) for item in resources)
        metric_count = sum(len(item.metrics) for item in resources)

        self.stdout.write("AskLens registry summary")
        self.stdout.write(f"Resources: {resource_count}")
        self.stdout.write(f"Global resources: {global_count}")
        self.stdout.write(f"Context-scoped resources: {scoped_count}")
        self.stdout.write(f"Fields: {field_count}")
        self.stdout.write(f"Metrics: {metric_count}")
        self.stdout.write(f"Status: {'OK' if resources else 'EMPTY'}")

        if not resources and options["fail_on_empty"]:
            raise CommandError("AskLens registry is empty.")
