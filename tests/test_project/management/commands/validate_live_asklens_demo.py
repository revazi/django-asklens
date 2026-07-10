"""Run an opt-in AskLens live/demo validation matrix."""

from collections.abc import Iterable, Mapping
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIClient

from django_asklens.catalog.registry import default_registry
from django_asklens.settings import get_asklens_setting
from tests.test_project.asklens_registry import ensure_complex_resources_registered

DEFAULT_USERS = ("admin",)
DEMO_USERS = (
    "admin",
    "facility-owner",
    "north-billing",
    "south-billing",
    "mixed-reporter",
    "schedule-reporter",
    "support-reporter",
    "no-report",
)
DEFAULT_QUESTIONS = (
    "What payment questions can I ask?",
    "Help me write revenue trend questions.",
    "Trend the number of member subscriptions by month using their start date.",
    "Trend paid billing revenue by month.",
    "Show failed payment attempts by billing status.",
)


class Command(BaseCommand):
    """Exercise the runnable demo through the AskLens API."""

    help = (
        "Run an opt-in synthetic AskLens demo validation matrix. Intended for "
        "manual live LLM checks; default tests do not call this command."
    )

    def add_arguments(self, parser) -> None:
        """Configure command-line options."""

        parser.add_argument(
            "--user",
            dest="users",
            action="append",
            help="Seeded demo username to validate. Can be provided multiple times.",
        )
        parser.add_argument(
            "--all-users",
            action="store_true",
            help="Validate all seeded demo users.",
        )
        parser.add_argument(
            "--question",
            dest="questions",
            action="append",
            help="Question to ask. Can be provided multiple times.",
        )
        parser.add_argument(
            "--allow-dummy",
            action="store_true",
            help="Allow dummy backend for offline smoke tests of the command itself.",
        )
        parser.add_argument(
            "--stop-on-failure",
            action="store_true",
            help="Raise CommandError after the first non-2xx AskLens response.",
        )

    def handle(self, *args, **options) -> None:
        """Run the validation matrix and print safe summaries."""

        ensure_complex_resources_registered()
        validate_backend(options["allow_dummy"])
        users = resolve_users(
            all_users=options["all_users"],
            configured_users=options.get("users"),
        )
        questions = tuple(options.get("questions") or DEFAULT_QUESTIONS)

        self.stdout.write(self.style.MIGRATE_HEADING("AskLens demo validation"))
        self.stdout.write(f"backend: {get_asklens_setting('LLM_BACKEND')}")
        if get_asklens_setting("LLM_MODEL"):
            self.stdout.write(f"model: {get_asklens_setting('LLM_MODEL')}")
        self.stdout.write(
            f"api key present: {bool(get_asklens_setting('LLM_API_KEY'))}"
        )
        self.stdout.write(f"registered resources: {len(default_registry.all())}")
        self.stdout.write(f"users: {', '.join(users)}")
        self.stdout.write(f"questions: {len(questions)}")

        for username in users:
            user = get_demo_user(username)
            self.stdout.write(self.style.HTTP_INFO(f"\nUSER {username}"))
            client = APIClient()
            client.force_authenticate(user=user)
            for question in questions:
                response = client.post(
                    "/asklens/query/",
                    {"question": question, "include_visualization": False},
                    format="json",
                )
                self.stdout.write(f"  Q: {question}")
                self.stdout.write(f"    {summarize_response(response)}")
                if options["stop_on_failure"] and response.status_code >= 400:
                    raise CommandError(
                        f"AskLens validation failed for {username}: {question}"
                    )


def validate_backend(allow_dummy: bool) -> None:
    """Require live mode unless the caller explicitly permits dummy mode."""

    backend = get_asklens_setting("LLM_BACKEND")
    if backend == "dummy" and not allow_dummy:
        msg = (
            "Demo validation is intended for live LLM mode. Set "
            "DJANGO_ASKLENS_DEMO_LIVE_LLM=1 and provider env vars, or pass "
            "--allow-dummy for an offline command smoke test."
        )
        raise CommandError(msg)
    if backend == "openai_compatible":
        if not get_asklens_setting("LLM_API_KEY"):
            raise CommandError("DJANGO_ASKLENS['LLM_API_KEY'] is not configured.")
        if not get_asklens_setting("LLM_MODEL"):
            raise CommandError("DJANGO_ASKLENS['LLM_MODEL'] is not configured.")


def resolve_users(
    *, all_users: bool, configured_users: Iterable[str] | None
) -> tuple[str, ...]:
    """Return usernames selected for validation."""

    if all_users:
        return DEMO_USERS
    users = tuple(configured_users or DEFAULT_USERS)
    if not users:
        return DEFAULT_USERS
    return users


def get_demo_user(username: str):
    """Return one seeded demo user or raise a clear command error."""

    user_model = get_user_model()
    try:
        return user_model.objects.get(username=username)
    except user_model.DoesNotExist as exc:
        msg = (
            f"Demo user {username!r} does not exist. Run "
            "`python -m django seed_complex_test_project` first."
        )
        raise CommandError(msg) from exc


def summarize_response(response) -> str:
    """Return a safe one-line response summary without row values or secrets."""

    payload: dict[str, Any] = getattr(response, "data", {}) or {}
    if response.status_code >= 400:
        return summarize_error(response.status_code, payload)

    if payload.get("response_type") == "capabilities":
        capabilities = payload.get("capabilities", {})
        query_help = payload.get("query_help", {})
        return (
            f"HTTP {response.status_code} capabilities "
            f"routing={payload.get('routing_source', 'unknown')} "
            f"help={payload.get('query_help_source', 'unknown')} "
            f"resources={len(capabilities.get('resources', []))} "
            f"suggestions={len(query_help.get('suggestions', []))}"
        )

    plan = payload.get("plan", {})
    columns = [column.get("key", "") for column in payload.get("columns", [])]
    return (
        f"HTTP {response.status_code} query "
        f"resource={plan.get('resource', 'unknown')} "
        f"intent={plan.get('intent', 'unknown')} "
        f"rows={payload.get('row_count', 0)} "
        f"columns={','.join(columns)}"
    )


def summarize_error(status_code: int, payload: Mapping[str, Any]) -> str:
    """Return a safe error summary."""

    error = payload.get("error") or payload.get("detail") or "Request failed"
    return f"HTTP {status_code} error={error}"
