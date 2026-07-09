# Multi-tenant security

AskLens does not include a tenant policy engine yet. Current multi-tenant support is provided through host-project resource registration and Django/DRF permissions.

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
        },
    },
    metrics=[Metric("order_count", op="count", field="id")],
    base_queryset=visible_orders,
)
```

Use this hook for tenant isolation and row-level visibility. Do not register resources with unrestricted querysets in multi-tenant apps.

## Field permissions

Fields marked `sensitive=True` are hidden from normal catalog serialization. If a sensitive field should be usable in results, opt it in explicitly with `result_visible=True` and protect it with `requires_permission`.

QueryPlan validation checks `request.user.get_all_permissions()` in the API flow. A crafted provider response that selects or filters a permission-gated field fails before ORM compilation unless the user has the required Django permission.

Catalog serialization is permission-scoped. The catalog endpoint and planner prompt include permission-gated sensitive fields only when the current user has the required Django permission. Metrics whose source field is hidden are also hidden.

## Route-level gates

All AskLens API views use `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`. Configure DRF permission classes appropriate for your project, for example staff-only, role-based, or feature-flagged access.

```python
DJANGO_ASKLENS = {
    "API_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

## Current limitations

- Live LLM providers are opt-in and should be validated against a private target project before public alpha.
- AskLens relies on host apps to define tenant membership and row-level queryset policy.
- Read-only database replica routing is deferred to a later phase.
