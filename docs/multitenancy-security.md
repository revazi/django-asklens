# Multi-tenant security

AskLens does not include a separate tenant policy engine in the alpha package surface. Current multi-tenant support is provided through explicit host-project scope providers and Django/DRF permissions.

## Tenant scoping with `scope_provider(request)`

Every resource must resolve to `global` or `context_scoped`. Projects can configure `DJANGO_ASKLENS["DEFAULT_SCOPE_MODE"] = "context_scoped"` once; `global` must always be declared individually. Context-scoped resources require a trusted request-aware provider, and AskLens compiles and executes plans from the returned queryset.

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
}
```

```python
from django_asklens import Metric, register


def visible_orders(request):
    account_ids = AccountMembership.objects.filter(
        user=request.user,
    ).values("account_id")
    return Order.objects.filter(account_id__in=account_ids)


register(
    timezone="UTC",
    model=Order,
    name="orders",
    fields={
        "id": {
            "binding": "id",
            "type": "integer",
            "nullable": False,
            "label": "Order ID",
        },
        "status": {
            "binding": "status",
            "type": "string",
            "nullable": False,
            "label": "Status",
        },
        "account.slug": {
            "binding": "account__slug",
            "type": "string",
            "nullable": False,
            "label": "Tenant",
            "sensitive": True,
            "result_visible": True,
            "requires_permission": "accounts.view_account",
            "scope_dimension": True,
        },
    },
    metrics=[
        Metric(
            "order_count",
            op="count",
            binding="id",
            result_type="integer",
        )
    ],
    requires_permission="orders.view_reports",
    scope_provider=visible_orders,
)
```

Use this provider for tenant isolation and row-level visibility. It must return an unevaluated `QuerySet` for the registered model; `none()` is valid. Missing request context, missing/invalid provider results, evaluated querysets, wrong models, and provider failures reject rather than falling back to the default manager. Use `scope_mode="global"` only for resources intentionally reviewed as unrestricted across rows.

Public field keys such as `account.slug` have no ORM meaning. The separately registered `account__slug` binding remains server-owned and is not included in catalogs, capabilities, provider prompts, plans, or results.

## Resource and field permissions

Use resource-level `requires_permission` on `register()` to hide and reject an entire resource unless the current request has the required permission string. Fields marked `sensitive=True` are hidden from normal catalog serialization. If a sensitive field should be usable in results, opt it in explicitly with `result_visible=True` and protect it with field-level `requires_permission`. Metrics over permission-sensitive data must declare their own `requires_permission`; their private binding does not implicitly inherit a public field policy.

By default, QueryPlan validation checks `request.user.get_all_permissions()` in the API flow. A crafted provider response that selects or filters a permission-gated field fails before ORM compilation unless the request has the required permission string.

Projects with role tables, tenant-scoped staff permissions, or non-Django permission systems can configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]` with a callable or import string. The callable receives the request and returns permission strings used for catalog serialization, planner prompts, API QueryPlan validation, and sanitized query-help/provider scope guidance. Machine capabilities are resource-independent.

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

For query-help UX, AskLens can infer generic row-scope breadth from scoped permission tokens shaped as `<scope-kind>:<opaque-scope-id>:<permission>`, for example `account:123:orders.view_reports`, `organization:abc:orders.view_reports`, or any other project-specific scope kind. The scope kind is used only for generic wording such as single-scope vs multi-scope guidance. Scope IDs are not included in catalog or query-help output or sent to providers; machine capabilities contain no scope metadata. If your schema names do not match the scope kind, mark fields with `scope_dimension=True` and resources with `scope_resource=True` during registration so help suggestions do not imply broader access than the request has.

## Route-level gates

All AskLens API views use `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`. The default gate is `django_asklens.access.IsAuthenticated`. API projects can configure DRF permission classes or other DRF-compatible classes appropriate for the project, for example staff-only, role-based, or feature-flagged access.

```python
DJANGO_ASKLENS = {
    "API_PERMISSION_CLASSES": ["django_asklens.access.IsAuthenticated"],
}
```

## Operational boundaries

- Live LLM providers are opt-in and should be validated in a safe non-production environment before production use.
- AskLens relies on host apps to define tenant membership and correct server-owned scope-provider policy.
- Read-only replica/database routing is a host-project deployment concern in alpha.
