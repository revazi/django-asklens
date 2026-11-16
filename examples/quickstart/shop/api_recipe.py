"""Installed API recipe: real session authentication, CSRF, and scoped results."""

import json

from django.test import Client, TestCase

from django_asklens.models import SemanticQueryRun
from shop.recipe_support import (
    ALICE_ROWS,
    EMPTY_QUESTION,
    PAID_QUESTION,
    assert_metadata_audit,
    assert_no_order_sql,
    csrf_post,
    seed,
    sign_in,
)


class APIRecipeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.url = "/asklens/query/"

    def query(self, question=PAID_QUESTION, **extra):
        return csrf_post(
            self.client, self.url, {"question": question, **extra}, api=True
        )

    def test_session_login_csrf_columns_data_empty_and_revocation(self):
        self.assertEqual(self.client.get("/table/").status_code, 302)
        self.assertEqual(self.client.get("/asklens/catalog/").status_code, 403)
        anonymous = assert_no_order_sql(
            lambda: self.client.post(
                self.url,
                json.dumps({"question": PAID_QUESTION}),
                content_type="application/json",
            )
        )
        self.assertEqual(anonymous.status_code, 403)
        self.assertEqual(SemanticQueryRun.objects.count(), 0)
        user = sign_in(self.client)
        self.assertEqual(self.client.get("/table/").status_code, 200)
        before = SemanticQueryRun.objects.count()
        no_csrf = self.client.post(
            self.url,
            json.dumps({"question": PAID_QUESTION}),
            content_type="application/json",
        )
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(
            no_csrf.json()["error"]["code"], "asklens.authorization.denied"
        )
        self.assertEqual(SemanticQueryRun.objects.count(), before)
        catalog = self.client.get("/asklens/catalog/").json()
        self.assertEqual([r["name"] for r in catalog["resources"]], ["orders"])
        self.assertNotIn("owner", json.dumps(catalog))
        self.assertNotIn("shop.view_order", json.dumps(catalog))
        success = self.query()
        self.assertEqual(success.status_code, 200)
        result = success.json()["result"]
        self.assertEqual(result["data"], ALICE_ROWS)
        self.assertEqual(
            [c["key"] for c in result["columns"]], ["product", "total_cents"]
        )
        self.assertFalse(result["result_metadata"]["truncated"])
        empty = self.query(EMPTY_QUESTION)
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["result"]["data"], [])
        user.user_permissions.clear()
        self.assertEqual(self.client.get("/asklens/catalog/").json(), {"resources": []})
        denied = assert_no_order_sql(self.query)
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(set(denied.json()), {"error", "run_id"})
        self.assertEqual(
            denied.json()["error"],
            {
                "code": "asklens.member.unavailable",
                "message": "A requested query member is unavailable.",
            },
        )
        unknown = assert_no_order_sql(
            lambda: self.query(
                plan={"resource": "missing", "intent": "list", "select": ["product"]}
            )
        )
        self.assertEqual(unknown.json()["error"], denied.json()["error"])
        self.assertEqual(unknown.status_code, denied.status_code)
        self.assertEqual(
            sorted(SemanticQueryRun.objects.values_list("status", flat=True)),
            ["failed", "failed", "success", "success"],
        )
        assert_metadata_audit()

    def test_client_policy_claims_rejected_before_execution(self):
        sign_in(self.client)
        for claim in ("user", "username", "permissions", "tenant", "scope"):
            response = assert_no_order_sql(
                lambda key=claim: self.query(**{key: "untrusted"})
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(SemanticQueryRun.objects.count(), 0)

    def test_second_authenticated_owner_has_only_their_rows(self):
        sign_in(self.client, "asklens-bob")
        self.assertEqual(
            self.query().json()["result"]["data"],
            [
                {"product": "South membership", "total_cents": 9900},
            ],
        )
