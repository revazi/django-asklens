"""Consumer-app regressions, runnable with Django alone (no pytest/extras)."""

import json
from contextlib import nullcontext
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from django_asklens.exceptions import LLMProviderError
from django_asklens.models import SemanticQueryRun
from shop.models import Order


class QuickstartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_quickstart", stdout=StringIO())

    def ask(self, question="Show my paid orders", user="alice"):
        output = StringIO()
        call_command("ask_orders", question, as_user=user, stdout=output)
        return json.loads(output.getvalue())

    def test_paid_question_is_scoped_and_ordered(self):
        alice = self.ask()["result"]
        self.assertEqual(
            alice["data"],
            [
                {"product": "North class", "total_cents": 2000},
                {"product": "North membership", "total_cents": 1200},
            ],
        )
        self.assertFalse(alice["result_metadata"]["truncated"])
        bob = self.ask(user="bob")["result"]
        self.assertEqual(
            bob["data"], [{"product": "South membership", "total_cents": 9900}]
        )

    def test_refunded_question_is_successful_empty_result(self):
        result = self.ask("Show my refunded orders")
        self.assertEqual(result["response_type"], "query")
        self.assertEqual(result["result"]["data"], [])
        self.assertEqual(result["result"]["row_count"], 0)
        self.assertTrue(result["result"]["columns"])
        self.assertFalse(result["result"]["result_metadata"]["truncated"])

    def test_denial_is_opaque_and_executes_no_order_queries(self):
        output = StringIO()
        with CaptureQueriesContext(connection) as queries:
            with self.assertRaises(CommandError):
                call_command(
                    "ask_orders",
                    "Show my paid orders",
                    as_user="no-report",
                    stdout=output,
                )
        response = json.loads(output.getvalue())
        self.assertEqual(response["response_type"], "error")
        self.assertEqual(response["error"]["code"], "asklens.member.unavailable")
        self.assertNotIn("shop.view_order", output.getvalue())
        self.assertFalse(any('"shop_order"' in q["sql"] for q in queries))
        self.assertEqual(SemanticQueryRun.objects.count(), 1)

    def test_arbitrary_wording_is_not_interpreted(self):
        for question in (
            "Find every order please",
            "show my paid orders",
            "Show my paid orders!",
            "<script>synthetic-private-question-187</script> tenant permission key",
        ):
            with self.subTest(question=question):
                SemanticQueryRun.objects.all().delete()
                output = StringIO()
                with CaptureQueriesContext(connection) as queries:
                    with self.assertRaises(CommandError):
                        call_command("ask_orders", question, stdout=output)
                self.assertEqual(
                    json.loads(output.getvalue()),
                    {
                        "response_type": "error",
                        "error": {
                            "code": "asklens.provider.failed",
                            "message": (
                                "The query provider could not produce "
                                "a usable response."
                            ),
                        },
                    },
                )
                self.assertFalse(any('"shop_order"' in q["sql"] for q in queries))
                run = SemanticQueryRun.objects.get()
                self.assertEqual(run.question, "")
                self.assertEqual(run.plan, {})
                self.assertNotIn(question, output.getvalue() + run.error)

    def test_failed_exact_questions_are_safe_and_metadata_only(self):
        """Reproduce fixture/config/provider failures through the actual consumer."""

        private = "synthetic-private-187 <script>hostile</script> tenant permission key"
        cases = (
            (
                "malformed-envelope",
                {"DUMMY_PLANS": {"Show my paid orders": {"private": private}}},
                None,
                "asklens.plan.invalid",
                "The query plan is invalid.",
            ),
            (
                "invalid-configuration",
                {"DUMMY_PLANS": private},
                None,
                "asklens.provider.failed",
                "The query provider could not produce a usable response.",
            ),
            (
                "provider-failure",
                {},
                LLMProviderError(private),
                "asklens.provider.failed",
                "The query provider could not produce a usable response.",
            ),
        )
        for label, configuration, failure, code, message in cases:
            with self.subTest(label=label):
                SemanticQueryRun.objects.all().delete()
                output = StringIO()
                with (
                    override_settings(
                        DJANGO_ASKLENS={**settings.DJANGO_ASKLENS, **configuration}
                    ),
                    patch(
                        "django_asklens.llms.openai_compatible."
                        "OpenAICompatibleProvider.complete_json",
                        side_effect=AssertionError("No live provider is allowed"),
                    ),
                ):
                    # Only the provider-failure case replaces the dummy call;
                    # the others exercise the real deterministic parser/config.
                    provider_patch = (
                        patch(
                            "django_asklens.llms.dummy.DummyProvider.complete_json",
                            side_effect=failure,
                        )
                        if failure is not None
                        else nullcontext()
                    )
                    with provider_patch, CaptureQueriesContext(connection) as queries:
                        with self.assertRaises(CommandError):
                            call_command(
                                "ask_orders", "Show my paid orders", stdout=output
                            )
                self.assertEqual(
                    json.loads(output.getvalue()),
                    {
                        "response_type": "error",
                        "error": {"code": code, "message": message},
                    },
                )
                self.assertFalse(any('"shop_order"' in q["sql"] for q in queries))
                run = SemanticQueryRun.objects.get()
                self.assertEqual(run.question, "")
                self.assertEqual(run.plan, {})
                self.assertEqual(run.status, SemanticQueryRun.Status.FAILED)
                self.assertEqual(run.row_count, 0)
                self.assertEqual(run.error, f"{code}: {message}")
                self.assertNotIn(private, output.getvalue() + str(run.plan) + run.error)

    def test_audit_defaults_do_not_persist_question_or_full_plan(self):
        self.ask()
        run = SemanticQueryRun.objects.get()
        self.assertEqual(run.question, "")
        self.assertNotIn("filters", run.plan)
        self.assertNotIn("select", run.plan)
        self.assertNotIn("Show my paid orders", str(run.plan))

    def test_seed_is_repeatable_and_accounts_cannot_log_in(self):
        call_command("seed_quickstart", stdout=StringIO())
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(get_user_model().objects.count(), 3)
        for user in get_user_model().objects.all():
            self.assertFalse(user.has_usable_password())
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)

    def test_seed_refuses_existing_password_account(self):
        user = get_user_model().objects.get(username="asklens-alice")
        user.set_password("synthetic-changed-password")
        user.save()
        with self.assertRaises(CommandError):
            call_command("seed_quickstart", stdout=StringIO())

    def test_unknown_user_selector_is_rejected_by_cli(self):
        with self.assertRaises(CommandError):
            call_command("ask_orders", "Show my paid orders", "--as-user", "admin")
