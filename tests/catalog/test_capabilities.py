"""Tests for permission-scoped AskLens capabilities guidance."""

from django_asklens.catalog.capabilities import build_capabilities


def test_build_capabilities_handles_empty_catalog() -> None:
    """An empty visible catalog should produce clear guidance, not an error."""

    capabilities = build_capabilities(catalog={"resources": []})

    assert (
        capabilities["summary"]
        == "No AskLens resources are queryable for this request."
    )
    assert capabilities["resources"] == []
    assert capabilities["examples"] == []
    assert "raw SQL" in " ".join(capabilities["limitations"])


def test_build_capabilities_describes_visible_fields_metrics_and_examples() -> None:
    """Capabilities should be derived from safe catalog metadata only."""

    capabilities = build_capabilities(
        catalog={
            "resources": [
                {
                    "name": "orders",
                    "label": "Orders",
                    "description": "Customer orders.",
                    "synonyms": ["purchases"],
                    "default_date_field": "created_at",
                    "fields": [
                        {
                            "name": "status",
                            "label": "Status",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "created_at",
                            "label": "Created date",
                            "type": "datetime",
                            "relation_depth": 0,
                        },
                        {
                            "name": "internal_code",
                            "label": "Internal code",
                            "type": "string",
                            "relation_depth": 0,
                            "result_visible": False,
                        },
                    ],
                    "metrics": [
                        {
                            "name": "order_count",
                            "label": "Order count",
                            "op": "count",
                            "field": "status",
                        }
                    ],
                }
            ]
        }
    )

    [resource] = capabilities["resources"]
    assert resource["name"] == "orders"
    assert resource["fields"][0]["can_select"] is True
    assert resource["fields"][1]["can_date_bucket"] is True
    assert resource["fields"][2]["can_select"] is False
    assert resource["metrics"] == [
        {
            "name": "order_count",
            "label": "Order count",
            "op": "count",
            "field": "status",
        }
    ]
    assert (
        "List Orders with Status, Created date, and Internal code"
        not in resource["examples"]
    )
    assert "Show count of Orders by Status" in resource["examples"]
    assert "Trend Order count by month using Created date" in resource["examples"]
    assert capabilities["examples"] == resource["examples"]


def test_build_capabilities_includes_configured_row_limit_guidance(settings) -> None:
    """Capabilities should guide users to narrow broad list results."""

    settings.DJANGO_ASKLENS = {"MAX_ROWS": 25}

    capabilities = build_capabilities(catalog={"resources": []})

    assert any("25 rows" in item for item in capabilities["limitations"])
    assert any("25-row" in item for item in capabilities["query_patterns"])


def test_build_capabilities_adds_sanitized_single_scope_guidance() -> None:
    """Capabilities can guide LLM help without leaking scope identifiers."""

    capabilities = build_capabilities(
        permissions={"facility:123:BillingReportsView"},
        catalog={
            "resources": [
                {
                    "name": "billing_lines",
                    "label": "Billing lines",
                    "description": "Billing facts.",
                    "synonyms": [],
                    "default_date_field": "created_at",
                    "requires_permission": "BillingReportsView",
                    "fields": [
                        {
                            "name": "facility.name",
                            "label": "Facility",
                            "type": "string",
                            "relation_depth": 1,
                        },
                        {
                            "name": "product_name",
                            "label": "Product",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "created_at",
                            "label": "Created date",
                            "type": "datetime",
                            "relation_depth": 0,
                        },
                    ],
                    "metrics": [
                        {
                            "name": "gross_revenue",
                            "label": "Gross revenue",
                            "op": "sum",
                            "field": "product_name",
                        }
                    ],
                }
            ]
        },
    )

    [resource] = capabilities["resources"]
    assert resource["scope"]["level"] == "single"
    assert resource["scope"]["kind"] == "facility"
    assert "facility:123" not in str(capabilities)
    assert all("Facility" not in example for example in resource["examples"])
    assert "Show Gross revenue by Product" in resource["examples"]


def test_build_capabilities_omits_single_scope_resource_examples() -> None:
    """Single-facility users should not get plural facility-list suggestions."""

    capabilities = build_capabilities(
        permissions={"facility:123:FacilityView"},
        catalog={
            "resources": [
                {
                    "name": "facilities",
                    "label": "Facilities",
                    "description": "Visible facilities.",
                    "synonyms": [],
                    "default_date_field": "created_at",
                    "requires_permission": "FacilityView",
                    "fields": [
                        {
                            "name": "name",
                            "label": "Facility name",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "timezone",
                            "label": "Timezone",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "is_active",
                            "label": "Active status",
                            "type": "boolean",
                            "relation_depth": 0,
                        },
                    ],
                    "metrics": [
                        {
                            "name": "facility_count",
                            "label": "Facilities",
                            "op": "count",
                            "field": "name",
                        }
                    ],
                }
            ]
        },
    )

    [resource] = capabilities["resources"]
    assert resource["scope"]["level"] == "single"
    assert resource["examples"] == []
    assert capabilities["examples"] == []
    assert "List Facilities with Facility name" not in str(capabilities)


def test_build_capabilities_honors_examples_enabled_flag() -> None:
    """Utility resources can stay visible without generated question examples."""

    capabilities = build_capabilities(
        catalog={
            "resources": [
                {
                    "name": "owner_lookup",
                    "label": "Owner lookup",
                    "description": "Owner lookup.",
                    "synonyms": [],
                    "default_date_field": None,
                    "examples_enabled": False,
                    "fields": [
                        {
                            "name": "owner_name",
                            "label": "Owner name",
                            "type": "string",
                            "relation_depth": 0,
                        }
                    ],
                    "metrics": [],
                }
            ]
        }
    )

    [resource] = capabilities["resources"]
    assert resource["name"] == "owner_lookup"
    assert resource["examples_enabled"] is False
    assert resource["examples"] == []
    assert capabilities["examples"] == []


def test_build_capabilities_uses_explicit_scope_metadata_for_arbitrary_names() -> None:
    """Scope help should not depend on facility/account/tenant naming."""

    capabilities = build_capabilities(
        permissions={"gym:abc:ReportsView"},
        catalog={
            "resources": [
                {
                    "name": "locations",
                    "label": "Studios",
                    "description": "Visible studios.",
                    "synonyms": [],
                    "default_date_field": "opened_at",
                    "requires_permission": "ReportsView",
                    "scope_resource": True,
                    "fields": [
                        {
                            "name": "display_name",
                            "label": "Display name",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "opened_at",
                            "label": "Opened date",
                            "type": "datetime",
                            "relation_depth": 0,
                        },
                    ],
                    "metrics": [
                        {
                            "name": "studio_count",
                            "label": "Studios",
                            "op": "count",
                            "field": "display_name",
                        }
                    ],
                },
                {
                    "name": "bookings",
                    "label": "Bookings",
                    "description": "Bookings.",
                    "synonyms": [],
                    "default_date_field": "booked_at",
                    "requires_permission": "ReportsView",
                    "fields": [
                        {
                            "name": "home_box.label",
                            "label": "Home box",
                            "type": "string",
                            "relation_depth": 1,
                            "scope_dimension": True,
                        },
                        {
                            "name": "status",
                            "label": "Status",
                            "type": "string",
                            "relation_depth": 0,
                        },
                        {
                            "name": "booked_at",
                            "label": "Booked date",
                            "type": "datetime",
                            "relation_depth": 0,
                        },
                    ],
                    "metrics": [
                        {
                            "name": "booking_count",
                            "label": "Bookings",
                            "op": "count",
                            "field": "status",
                        }
                    ],
                },
            ]
        },
    )

    resources = {resource["name"]: resource for resource in capabilities["resources"]}
    assert resources["locations"]["scope"]["level"] == "single"
    assert resources["locations"]["examples"] == []
    assert resources["bookings"]["fields"][0]["scope_dimension"] is True
    assert "Home box" not in str(resources["bookings"]["examples"])
    assert "Show count of Bookings by Status" in resources["bookings"]["examples"]
