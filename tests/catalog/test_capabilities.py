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
