"""Django-only admin recipe; run explicitly with quickstart.web_settings."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from django_asklens.models import SemanticQueryRun
from shop.recipe_support import (
    EMPTY_QUESTION,
    PAID_QUESTION,
    assert_metadata_audit,
    assert_no_order_sql,
    csrf_post,
    permission,
    seed,
    sign_in,
)


class AdminRecipeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        user = get_user_model().objects.create_user("recipe-staff", is_staff=True)
        user.user_permissions.add(permission())
        # Same trusted ownership policy as CLI/API; do not grant global scope.
        from shop.models import Order

        alice = get_user_model().objects.get(username="asklens-alice")
        Order.objects.filter(owner=alice).update(owner=user)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse("admin:asklens_asklensquery_changelist")

    def test_login_csrf_table_empty_and_current_permission_denial(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        user = sign_in(self.client, "recipe-staff", "/admin/login/")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        before = SemanticQueryRun.objects.count()
        self.assertEqual(
            self.client.post(self.url, {"question": PAID_QUESTION}).status_code, 403
        )
        self.assertEqual(SemanticQueryRun.objects.count(), before)
        success = csrf_post(self.client, self.url, {"question": PAID_QUESTION})
        self.assertContains(success, "North class")
        self.assertNotContains(success, "South membership")
        self.assertContains(success, '<th scope="col">Product</th>', html=True)
        self.assertEqual(success.context["result"]["row_count"], 2)
        empty = csrf_post(self.client, self.url, {"question": EMPTY_QUESTION})
        self.assertContains(empty, "No rows")
        self.assertEqual(empty.context["result"]["row_count"], 0)
        user.user_permissions.clear()
        denied = assert_no_order_sql(
            lambda: csrf_post(self.client, self.url, {"question": PAID_QUESTION})
        )
        self.assertEqual(denied.status_code, 200)  # Form renders the safe error.
        self.assertIsNone(denied.context["result"])
        self.assertEqual(
            denied.context["error"], "A requested query member is unavailable."
        )
        self.assertNotContains(denied, "shop.view_order")
        self.assertNotContains(denied, "North class")
        self.assertEqual(
            sorted(SemanticQueryRun.objects.values_list("status", flat=True)),
            ["failed", "success", "success"],
        )
        assert_metadata_audit()

    def test_shared_route_gate_denies_before_orchestration(self):
        sign_in(self.client, "recipe-staff", "/admin/login/")
        self.client.get(self.url)
        from django.conf import settings

        with self.settings(
            DJANGO_ASKLENS={
                **settings.DJANGO_ASKLENS,
                "API_PERMISSION_CLASSES": [DenyAccess],
            }
        ):
            response = assert_no_order_sql(
                lambda: csrf_post(self.client, self.url, {"question": PAID_QUESTION})
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SemanticQueryRun.objects.count(), 0)

    def test_audit_admin_stays_view_only_even_for_superuser(self):
        user = get_user_model().objects.get(username="recipe-staff")
        user.is_superuser = True
        user.save()
        sign_in(self.client, "recipe-staff", "/admin/login/")
        run = SemanticQueryRun.objects.create(
            user=user,
            question="",
            plan={"resource": "orders", "intent": "list"},
            status="success",
            row_count=0,
            duration_ms=1,
        )
        detail = reverse("admin:asklens_semanticqueryrun_change", args=[run.pk])
        response = self.client.get(detail)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, 'class="deletelink"')
        for url in (
            detail,
            reverse("admin:asklens_semanticqueryrun_add"),
            reverse("admin:asklens_semanticqueryrun_delete", args=[run.pk]),
        ):
            self.assertEqual(
                csrf_post(self.client, url, {"post": "yes"}).status_code, 403
            )
        request = RequestFactory().get(detail)
        request.user = user
        model_admin = admin.site._registry[SemanticQueryRun]
        self.assertNotIn("delete_selected", model_admin.get_actions(request))
        self.assertEqual(SemanticQueryRun.objects.count(), 1)


class DenyAccess:
    def has_permission(self, request, view=None):
        return False
