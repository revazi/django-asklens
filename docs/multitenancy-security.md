# Multi-tenant security

AskLens does not include a separate tenant policy engine in the alpha package surface. Current multi-tenant support is provided through host-project resource registration and Django/DRF permissions.

## Tenant scoping with `base_queryset(request)`

Every registered resource can define a request-aware base queryset. AskLens compiles and executes plans from this queryset.

```python
from django_asklens import Metric, register


def visible_orders(request):
    account_ids = AccountMembership.objects.filter(
        user=request.user,
    ).values("account_id")
    return Order.objects.filter(account_id__in=account_ids)


register(
    model=Order,
    name="orders",
    fields={
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "account.slug": {
            "label": "Tenant",
            "sensitive": True,
            "result_visible": True,
            "requires_permission": "accounts.view_account",
            "scope_dimension": True,
        },
    },
    metrics=[Metric("order_count", op="count", field="id")],
    requires_permission="orders.view_reports",
    base_queryset=visible_orders,
)
```

Use this hook for tenant isolation and row-level visibility. Do not register resources with unrestricted querysets in multi-tenant apps.

## Resource and field permissions

Use resource-level `requires_permission` on `register()` to hide and reject an entire resource unless the current request has the required permission string. Fields marked `sensitive=True` are hidden from normal catalog serialization. If a sensitive field should be usable in results, opt it in explicitly with `result_visible=True` and protect it with field-level `requires_permission`.

By default, QueryPlan validation checks `request.user.get_all_permissions()` in the API flow. A crafted provider response that selects or filters a permission-gated field fails before ORM compilation unless the request has the required permission string.

Projects with role tables, tenant-scoped staff permissions, or non-Django permission systems can configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]` with a callable or import string. The callable receives the request and returns permission strings used for catalog serialization, planner prompts, API QueryPlan validation, and sanitized capabilities scope guidance.

```python
DJANGO_ASKLENS = {
    "REQUEST_PERMISSIONS_GETTER": "project.asklens_permissions.get_request_permissions",
}
```

```python
# project/asklens_permissions.py


def get_request_permissions(request):
    permissions = set()
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        permissions.update(user.get_all_permissions())

    role = getattr(request, "role", None)
    if role:
        permissions.add(f"role:{role}")

    staff = getattr(request, "staff", None)
    if staff is not None:
        permissions.update(staff.permissions.values_list("name", flat=True))

    return permissions
```

Catalog serialization is permission-scoped. The catalog endpoint and planner prompt include permission-gated sensitive fields only when the configured permission getter returns the required permission string. Metrics whose source field is hidden are also hidden.

For capabilities/help UX, AskLens can infer generic row-scope breadth from scoped permission tokens shaped as `<scope-kind>:<opaque-scope-id>:<permission>`, for example `account:123:orders.view_reports`, `organization:abc:orders.view_reports`, or any other project-specific scope kind. The scope kind is used only for generic wording such as single-scope vs multi-scope guidance. Scope IDs are not included in capabilities output or sent to providers. If your schema names do not match the scope kind, mark fields with `scope_dimension=True` and resources with `scope_resource=True` during registration so help suggestions do not imply broader access than the request has.

## Route-level gates

All AskLens API views use `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`. Configure DRF permission classes appropriate for your project, for example staff-only, role-based, or feature-flagged access.

```python
DJANGO_ASKLENS = {
    "API_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

## Operational boundaries

- Live LLM providers are opt-in and should be validated in a safe non-production environment before production use.
- AskLens relies on host apps to define tenant membership and row-level queryset policy.
- Read-only replica/database routing is a host-project deployment concern in alpha.
