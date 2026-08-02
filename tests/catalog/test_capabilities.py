"""Tests for separate machine capabilities and human query guidance."""

import pytest

from django_asklens.catalog.capabilities import (
    build_capabilities,
    build_query_guidance,
)


def test_machine_capabilities_exclude_catalog_and_human_guidance(settings) -> None:
    settings.DJANGO_ASKLENS = {
        "MAX_ROWS": 25,
        "DEFAULT_LIMIT": 10,
        "MAX_FILTERS": 7,
    }

    capabilities = build_capabilities()

    assert set(capabilities) == {
        "intents",
        "filter_logic",
        "types",
        "time_grains",
        "limits",
        "features",
        "aggregate_policies",
        "backend_restrictions",
    }
    assert capabilities["intents"] == ["list", "aggregate"]
    assert capabilities["filter_logic"] == "implicit_and"
    assert capabilities["types"][0] == {
        "name": "string",
        "operators": ["eq", "neq", "contains", "icontains", "in", "isnull"],
    }
    assert [item["name"] for item in capabilities["types"]] == [
        "string",
        "boolean",
        "integer",
        "decimal",
        "float",
        "date",
        "datetime",
        "time",
        "uuid",
        "enum",
    ]
    assert capabilities["time_grains"] == [
        "day",
        "week",
        "month",
        "quarter",
        "year",
    ]
    assert set(capabilities["limits"]) == {
        "max_plan_bytes",
        "max_filters",
        "max_selected_fields",
        "max_order_terms",
        "max_group_terms",
        "max_metrics",
        "max_relationship_hops",
        "max_relationship_edges",
        "max_in_values",
        "max_filter_values",
        "max_result_rows",
        "default_result_limit",
    }
    assert capabilities["limits"]["max_result_rows"] == 25
    assert capabilities["limits"]["default_result_limit"] == 10
    assert capabilities["limits"]["max_filters"] == 7
    assert set(capabilities["features"]) == {
        "registered_metrics",
        "presentation",
        "accurate_truncation",
        "raw_sql",
        "mutations",
        "cross_resource_queries",
        "arbitrary_expressions",
        "cursor_pagination",
    }
    assert capabilities["features"]["registered_metrics"] is True
    assert capabilities["features"]["raw_sql"] is False
    assert capabilities["backend_restrictions"] == []
    with pytest.raises(TypeError):
        build_capabilities(permissions=set())  # type: ignore[call-arg]
    assert (
        not {
            "summary",
            "resources",
            "examples",
            "guidance",
            "labels",
            "descriptions",
        }
        & capabilities.keys()
    )


def test_build_query_guidance_handles_empty_catalog() -> None:
    """An empty visible catalog should produce clear guidance, not an error."""

    capabilities = build_query_guidance(catalog={"resources": []})

    assert (
        capabilities["summary"]
        == "No AskLens resources are queryable for this request."
    )
    assert capabilities["resources"] == []
    assert capabilities["examples"] == []
    assert "raw SQL" in " ".join(capabilities["limitations"])


def test_build_query_guidance_describes_visible_fields_metrics_and_examples() -> None:
    """Guidance should be derived from safe catalog metadata only."""

    capabilities = build_query_guidance(
        catalog={
            "resources": [
                {
                    "name": "orders",
                    "label": "Orders",
                    "description": "Customer orders.",
                    "synonyms": ["purchases"],
                    "default_date_field": "created_at",
                    "timezone": "UTC",
                    "fields": [
                        {
                            "name": "status",
                            "label": "Status",
                            "type": "enum",
                            "nullable": False,
                            "relation_depth": 0,
                            "enum": {
                                "type": "string",
                                "values": [
                                    {
                                        "value": "paid",
                                        "label": "Paid",
                                        "aliases": ["settled"],
                                    },
                                    {"value": "pending", "label": "Pending"},
                                ],
                            },
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
                            "result_type": "integer",
                        }
                    ],
                }
            ]
        }
    )

    [resource] = capabilities["resources"]
    assert resource["name"] == "orders"
    assert resource["timezone"] == "UTC"
    assert resource["fields"][0]["can_select"] is True
    assert resource["fields"][0]["nullable"] is False
    assert resource["fields"][0]["operators"] == ["eq", "neq", "in", "isnull"]
    assert resource["fields"][0]["enum"] == {
        "type": "string",
        "values": [
            {"value": "paid", "label": "Paid", "aliases": ["settled"]},
            {"value": "pending", "label": "Pending"},
        ],
    }
    assert resource["fields"][1]["can_date_bucket"] is True
    assert "date_range" in resource["fields"][1]["operators"]
    assert resource["fields"][2]["can_select"] is False
    assert resource["metrics"] == [
        {
            "name": "order_count",
            "label": "Order count",
            "result_type": "integer",
        }
    ]
    assert (
        "List Orders with Status, Created date, and Internal code"
        not in resource["examples"]
    )
    assert "Show Order count by Status" in resource["examples"]
    assert "Trend Order count by month using Created date" in resource["examples"]
    assert capabilities["examples"] == resource["examples"]


def test_build_query_guidance_includes_configured_row_limit(settings) -> None:
    """Human guidance should reflect the configured broad-list limit."""

    settings.DJANGO_ASKLENS = {"MAX_ROWS": 25}

    capabilities = build_query_guidance(catalog={"resources": []})

    assert any("25 rows" in item for item in capabilities["limitations"])
    assert any("25-row" in item for item in capabilities["query_patterns"])


def test_build_query_guidance_adds_sanitized_single_scope_context() -> None:
    """Guidance can help the LLM without leaking scope identifiers."""

    capabilities = build_query_guidance(
        permissions={"facility:123:BillingReportsView"},
        resource_permissions={"billing_lines": "BillingReportsView"},
        catalog={
            "resources": [
                {
                    "name": "billing_lines",
                    "label": "Billing lines",
                    "description": "Billing facts.",
                    "synonyms": [],
                    "default_date_field": "created_at",
                    "timezone": "UTC",
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
                            "result_type": "decimal",
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
    assert "BillingReportsView" not in str(capabilities)
    assert all("Facility" not in example for example in resource["examples"])
    assert "Show Gross revenue by Product" in resource["examples"]


def test_build_query_guidance_omits_single_scope_resource_examples() -> None:
    """Single-facility users should not get plural facility-list suggestions."""

    capabilities = build_query_guidance(
        permissions={"facility:123:FacilityView"},
        resource_permissions={"facilities": "FacilityView"},
        catalog={
            "resources": [
                {
                    "name": "facilities",
                    "label": "Facilities",
                    "description": "Visible facilities.",
                    "synonyms": [],
                    "default_date_field": "created_at",
                    "timezone": "UTC",
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
                            "result_type": "integer",
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


def test_build_query_guidance_honors_examples_enabled_flag() -> None:
    """Utility resources can stay visible without generated question examples."""

    capabilities = build_query_guidance(
        catalog={
            "resources": [
                {
                    "name": "owner_lookup",
                    "label": "Owner lookup",
                    "description": "Owner lookup.",
                    "synonyms": [],
                    "default_date_field": None,
                    "timezone": "UTC",
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


def test_build_query_guidance_uses_explicit_scope_metadata() -> None:
    """Scope help should not depend on facility/account/tenant naming."""

    capabilities = build_query_guidance(
        permissions={"gym:abc:ReportsView"},
        resource_permissions={
            "locations": "ReportsView",
            "bookings": "ReportsView",
        },
        catalog={
            "resources": [
                {
                    "name": "locations",
                    "label": "Studios",
                    "description": "Visible studios.",
                    "synonyms": [],
                    "default_date_field": "opened_at",
                    "timezone": "UTC",
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
                            "result_type": "integer",
                        }
                    ],
                },
                {
                    "name": "bookings",
                    "label": "Bookings",
                    "description": "Bookings.",
                    "synonyms": [],
                    "default_date_field": "booked_at",
                    "timezone": "UTC",
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
                            "result_type": "integer",
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
    assert "Show Bookings by Status" in resources["bookings"]["examples"]
