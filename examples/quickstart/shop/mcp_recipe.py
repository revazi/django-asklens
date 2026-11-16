"""MCP-only installed recipe; server-context simulation, not wire authentication."""

import asyncio

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from quickstart.mcp import make_server, make_toolset

from django_asklens.models import SemanticQueryRun
from shop.recipe_support import (
    ALICE_ROWS,
    assert_metadata_audit,
    assert_no_order_sql,
    seed,
)

PLAN = {
    "resource": "orders",
    "intent": "list",
    "select": ["product", "total_cents"],
    "filters": [{"field": "status", "op": "eq", "value": "paid"}],
    "limit": 10,
}


class MCPRecipeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def setUp(self):
        self.session = object()
        self.user = get_user_model().objects.get(username="asklens-alice")
        # Synthetic host-owned session store. It is not a client context field.
        self.sessions = {self.session: self.user.pk}

        def authenticated_user_id(context):
            if context not in self.sessions:
                raise PermissionDenied("The current request is not authorized.")
            return self.sessions[context]

        self.resolve_identity = authenticated_user_id
        self.toolset = make_toolset(authenticated_user_id)

    def test_server_identity_default_omission_and_both_row_gates(self):
        discovery = self.toolset.asklens_capabilities(self.session)
        self.assertEqual(
            [r["name"] for r in discovery["resource_summaries"]], ["orders"]
        )
        before = SemanticQueryRun.objects.count()
        validation = assert_no_order_sql(
            lambda: self.toolset.asklens_validate_plan(self.session, PLAN)
        )
        self.assertTrue(validation["valid"])
        self.assertFalse(validation["executed"])
        self.assertEqual(SemanticQueryRun.objects.count(), before)
        omitted = self.toolset.asklens_execute_plan(self.session, PLAN)
        self.assertTrue(omitted["rows_omitted"])
        self.assertEqual(omitted["data"], [])
        self.assertEqual(omitted["row_count"], 2)
        denied_rows = self.toolset.asklens_execute_plan(
            self.session, PLAN, include_rows=True
        )
        self.assertTrue(denied_rows["row_return_denied"])
        self.assertEqual(denied_rows["data"], [])
        with self.settings(
            DJANGO_ASKLENS={
                **settings.DJANGO_ASKLENS,
                "MCP_ALLOW_ROW_RETURN": True,
                "MCP_MAX_RETURNED_ROWS": 1,
            }
        ):
            still_omitted = self.toolset.asklens_execute_plan(self.session, PLAN)
            self.assertTrue(still_omitted["rows_omitted"])
            returned = self.toolset.asklens_execute_plan(
                self.session, PLAN, include_rows=True
            )
            self.assertEqual(returned["data"], ALICE_ROWS[:1])
            self.assertEqual(returned["row_count"], 2)
            self.assertEqual(returned["mcp_returned_row_count"], 1)
            self.assertEqual(returned["mcp_row_limit"], 1)
            self.assertTrue(returned["mcp_rows_truncated"])
            self.assertFalse(returned["result_metadata"]["truncated"])
        # Previously validated plans do not authorize later execution.
        self.user.user_permissions.clear()
        denied = assert_no_order_sql(
            lambda: self.toolset.asklens_execute_plan(self.session, validation["plan"])
        )
        self.assertEqual(denied["error"]["code"], "asklens.member.unavailable")
        self.assertNotIn("shop.view_order", str(denied))
        self.assertNotIn("North class", str(denied))
        self.assertEqual(
            sorted(SemanticQueryRun.objects.values_list("status", flat=True)),
            ["failed", "success", "success", "success", "success"],
        )
        assert_metadata_audit()

    def test_expired_context_and_disabled_user_rejected_before_query(self):
        with self.assertRaises(PermissionDenied):
            assert_no_order_sql(lambda: self.toolset.asklens_capabilities(object()))
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            assert_no_order_sql(
                lambda: self.toolset.asklens_execute_plan(self.session, PLAN)
            )
        self.assertEqual(SemanticQueryRun.objects.count(), 0)

    def test_fastmcp_tools_have_no_client_identity_or_scope_arguments(self):
        server = make_server(self.resolve_identity)
        tools = asyncio.run(server.list_tools())
        self.assertEqual(len(tools), 5)
        self.assertNotIn("asklens_query", [tool.name for tool in tools])
        for tool in tools:
            self.assertFalse(
                set(tool.parameters.get("properties", {}))
                & {
                    "ctx",
                    "context",
                    "user",
                    "username",
                    "permissions",
                    "tenant",
                    "scope",
                }
            )
