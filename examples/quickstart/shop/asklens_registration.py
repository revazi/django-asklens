"""Public semantic fields stay separate from private host bindings and scope."""

from django_asklens import register

from .models import Order


def visible_orders(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return Order.objects.none()
    return Order.objects.filter(owner_id=user.pk)


register(
    model=Order,
    name="orders",
    label="My orders",
    description="Synthetic orders owned by the current authenticated user.",
    timezone="UTC",
    fields={
        "product": {
            "binding": "product",
            "type": "string",
            "nullable": False,
            "label": "Product",
        },
        "status": {
            "binding": "status",
            "type": "string",
            "nullable": False,
            "label": "Status",
        },
        "total_cents": {
            "binding": "total_cents",
            "type": "integer",
            "nullable": False,
            "label": "Total (cents)",
        },
    },
    default_order=(("product", "asc"),),
    requires_permission="shop.view_order",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
