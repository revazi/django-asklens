"""Committed Playwright evidence for the synthetic PostgreSQL reference demo."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from playwright.sync_api import (
    APIResponse,
    BrowserContext,
    Playwright,
    expect,
    sync_playwright,
)

DEMO_PASSWORD = "12admin34"
EXPECTED_OWNER_RESOURCES = {
    "billing_lines",
    "facilities",
    "facility_owners",
    "leads",
    "marketing_campaigns",
    "member_contacts",
    "member_statuses",
    "member_subscriptions",
    "members",
    "payment_attempts",
    "schedule_sessions",
    "session_bookings",
    "staff_shifts",
    "support_tickets",
}


def response_json(response: APIResponse, *, expected_status: int = 200) -> Any:
    """Return JSON after checking one Playwright network response."""

    assert response.status == expected_status
    return response.json()


def post_json(
    context: BrowserContext,
    url: str,
    payload: dict[str, Any],
    *,
    csrf_token: str,
    expected_status: int = 200,
) -> Any:
    """POST JSON through Playwright's browser-context request facility."""

    return response_json(
        context.request.post(
            url,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": csrf_token,
            },
        ),
        expected_status=expected_status,
    )


def assert_no_private_metadata(value: Any) -> None:
    """Reject backend and policy bindings anywhere in a public document."""

    forbidden = {
        "binding",
        "distinct_key",
        "model",
        "permissions",
        "requires_permission",
        "scope_provider",
        "tenant_id",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            assert_no_private_metadata(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_private_metadata(child)


def login(
    context: BrowserContext,
    base_url: str,
    username: str,
) -> tuple[Any, APIResponse | None]:
    """Log into the real Django admin form through a browser page."""

    page = context.new_page()
    initial = page.goto(f"{base_url}/", wait_until="domcontentloaded")
    assert initial is not None and initial.status == 200
    expect(page.locator("#id_username")).to_be_visible()
    page.locator("#id_username").fill(username)
    page.locator("#id_password").fill(DEMO_PASSWORD)
    with page.expect_navigation(wait_until="domcontentloaded") as navigation:
        page.get_by_role("button", name="Log in").click()
    return page, navigation.value


def verify_browser_and_api(playwright: Playwright, base_url: str) -> None:
    """Verify the demo UI and authenticated HTTP API with Playwright."""

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    try:
        unauthenticated = context.request.get(f"{base_url}/asklens/catalog/")
        assert unauthenticated.status in {401, 403}

        page, navigation = login(context, base_url, "facility-owner")
        assert navigation is not None and navigation.status == 200
        expect(page.get_by_role("heading", name="AskLens", exact=True)).to_be_visible()
        page.locator('details[aria-label="Current session"] summary').click()
        expect(page.get_by_text("Offline dummy plans", exact=True)).to_be_visible()
        expect(page.locator("#scope-list")).to_contain_text("North Studio")
        assert "South Studio" not in page.locator("#scope-list").inner_text()

        page.locator('details[aria-label="Visible catalog"] summary').click()
        expect(page.locator("#capabilities-list")).to_contain_text(
            "Billing lines", timeout=15_000
        )
        csrf_token = page.locator('[name="csrfmiddlewaretoken"]').input_value()

        catalog = response_json(context.request.get(f"{base_url}/asklens/catalog/"))
        resources = {resource["name"] for resource in catalog["resources"]}
        assert resources == EXPECTED_OWNER_RESOURCES
        assert_no_private_metadata(catalog)

        capabilities = response_json(
            context.request.get(f"{base_url}/asklens/capabilities/")
        )
        assert capabilities["intents"] == ["list", "aggregate"]
        assert capabilities["filter_logic"] == "implicit_and"
        assert capabilities["features"]["raw_sql"] is False
        assert "resources" not in capabilities
        assert "examples" not in capabilities
        assert_no_private_metadata(capabilities)
        print("PASS browser login, registration catalog, and machine capabilities")

        # Exercise the real frontend form, not only HTTP helpers.
        question = "Show paid billing revenue by product"
        page.locator("#question-input").fill(question)
        page.locator("#send-button").click()
        expect(page.locator("#composer-status")).to_have_text("Done.", timeout=20_000)
        result_card = page.locator(".result-card").last
        expect(result_card).to_contain_text("North membership")
        assert "South membership" not in result_card.inner_text()
        result_card.locator("details summary", has_text="Raw response").click()
        aggregate = json.loads(result_card.locator("details pre").inner_text())
        assert aggregate["response_type"] == "query"
        assert aggregate["plan"]["intent"] == "aggregate"
        assert aggregate["result_metadata"] == {
            "limit": 10,
            "limit_scope": "groups",
            "truncated": False,
        }
        aggregate_columns = {column["key"]: column for column in aggregate["columns"]}
        assert aggregate_columns["product_name"]["type"] == "string"
        assert aggregate_columns["gross_revenue"]["type"] == "integer"
        assert all(
            isinstance(row["gross_revenue"], int)
            and not isinstance(row["gross_revenue"], bool)
            for row in aggregate["data"]
        )
        assert all(
            row["product_name"].startswith("North ") for row in aggregate["data"]
        )

        aggregate_audit = response_json(
            context.request.get(f"{base_url}/asklens/runs/{aggregate['run_id']}/")
        )
        assert aggregate_audit["question"] == ""
        assert aggregate_audit["plan"] == {
            "resource": "billing_lines",
            "intent": "aggregate",
        }
        assert aggregate_audit["row_count"] == aggregate["row_count"]
        assert "product_name" not in aggregate_audit["plan"]
        print("PASS browser aggregate query and metadata-only audit")

        list_plan = {
            "resource": "members",
            "intent": "list",
            "select": [
                "facility.name",
                "gender",
                "member_since",
                "created_via_portal",
            ],
            "order_by": [{"field": "member_since", "direction": "asc"}],
            "limit": 3,
        }
        listed = post_json(
            context,
            f"{base_url}/asklens/query/",
            {"question": "Reference list query", "plan": list_plan},
            csrf_token=csrf_token,
        )
        assert listed["response_type"] == "query"
        assert listed["row_count"] == 3
        assert listed["result_metadata"] == {
            "limit": 3,
            "limit_scope": "rows",
            "truncated": True,
        }
        listed_columns = {column["key"]: column for column in listed["columns"]}
        assert {key: column["type"] for key, column in listed_columns.items()} == {
            "facility.name": "string",
            "gender": "enum",
            "member_since": "datetime",
            "created_via_portal": "boolean",
        }
        for row in listed["data"]:
            assert set(row) == set(listed_columns)
            assert row["facility.name"] == "North Studio"
            assert row["gender"] in {"female", "male", "non_binary", "not_provided"}
            member_since = datetime.fromisoformat(row["member_since"])
            assert member_since.utcoffset() is not None
            assert isinstance(row["created_via_portal"], bool)
        assert "South Studio" not in json.dumps(listed)
        assert_no_private_metadata(listed)

        listed_audit = response_json(
            context.request.get(f"{base_url}/asklens/runs/{listed['run_id']}/")
        )
        assert listed_audit["question"] == ""
        assert listed_audit["plan"] == {"resource": "members", "intent": "list"}
        assert listed_audit["error"] == ""
        print("PASS scoped list query, typed canonical JSON, and API run route")

        no_report_context = browser.new_context()
        try:
            denied_page, denied_navigation = login(
                no_report_context, base_url, "no-report"
            )
            assert denied_navigation is not None and denied_navigation.status == 403
            assert denied_page.url == f"{base_url}/"
            denied_catalog = no_report_context.request.get(
                f"{base_url}/asklens/catalog/"
            )
            assert denied_catalog.status == 403
        finally:
            no_report_context.close()
        print("PASS fail-closed no-report browser and API access")
    finally:
        context.close()
        browser.close()


def parse_json_rpc(response: APIResponse) -> dict[str, Any]:
    """Parse a JSON or SSE MCP Streamable HTTP response."""

    assert response.status == 200
    text = response.text()
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError("MCP response did not contain a JSON event")


def mcp_post(
    request: Any,
    base_url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[dict[str, Any], APIResponse]:
    """Send one real MCP Streamable HTTP request through Playwright."""

    response = request.post(
        f"{base_url}/mcp",
        data=payload,
        headers=headers,
    )
    return parse_json_rpc(response), response


def structured_tool_result(rpc_payload: dict[str, Any]) -> dict[str, Any]:
    """Return FastMCP structured content without relying on text rendering."""

    result = rpc_payload["result"]
    structured = result.get("structuredContent") or result.get("structured_content")
    if structured is not None:
        return structured
    for content in result.get("content", []):
        if content.get("type") == "text":
            return json.loads(content["text"])
    raise AssertionError("MCP tool result did not contain structured content")


def verify_fastmcp_http(playwright: Playwright, base_url: str) -> None:
    """Verify real FastMCP HTTP discovery and safe execution over Playwright."""

    request = playwright.request.new_context(
        extra_http_headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
    )
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    try:
        initialized, initialize_response = mcp_post(
            request,
            base_url,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "django-asklens-reference-playwright",
                        "version": "1",
                    },
                },
            },
            headers,
        )
        negotiated_version = initialized["result"]["protocolVersion"]
        headers["MCP-Protocol-Version"] = negotiated_version
        session_id = initialize_response.headers.get("mcp-session-id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        tools_rpc, _response = mcp_post(
            request,
            base_url,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers,
        )
        tools = {tool["name"]: tool for tool in tools_rpc["result"]["tools"]}
        assert set(tools) == {
            "asklens_capabilities",
            "asklens_describe_resource",
            "asklens_execute_plan",
            "asklens_query_plan_schema",
            "asklens_validate_plan",
        }
        execute_properties = tools["asklens_execute_plan"]["inputSchema"]["properties"]
        assert {"username", "user", "permissions", "tenant", "scope"}.isdisjoint(
            execute_properties
        )

        capabilities_rpc, _response = mcp_post(
            request,
            base_url,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "asklens_capabilities",
                    "arguments": {},
                },
            },
            headers,
        )
        mcp_capabilities = structured_tool_result(capabilities_rpc)
        assert mcp_capabilities["executed"] is False
        assert mcp_capabilities["rows_omitted"] is True
        summary_names = {
            resource["name"] for resource in mcp_capabilities["resource_summaries"]
        }
        assert summary_names == EXPECTED_OWNER_RESOURCES
        assert_no_private_metadata(mcp_capabilities)

        owner_plan = {
            "resource": "facility_owners",
            "intent": "list",
            "select": ["facility.name", "user.first_name", "user.last_name"],
            "order_by": [{"field": "facility.name", "direction": "asc"}],
            "limit": 20,
        }
        execution_rpc, _response = mcp_post(
            request,
            base_url,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "asklens_execute_plan",
                    "arguments": {"plan": owner_plan, "include_rows": True},
                },
            },
            headers,
        )
        execution = structured_tool_result(execution_rpc)
        assert execution["response_type"] == "query"
        assert execution["row_count"] == 1
        assert execution["data"] == []
        assert execution["rows_omitted"] is True
        assert execution["row_return_denied"] is True
        assert "North Studio" not in json.dumps(execution)
        assert "South Studio" not in json.dumps(execution)

        invalid_rpc, _response = mcp_post(
            request,
            base_url,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "asklens_validate_plan",
                    "arguments": {
                        "plan": {
                            "resource": "facility_owners",
                            "intent": "list",
                            "select": ["private_backend_field"],
                            "limit": 1,
                        }
                    },
                },
            },
            headers,
        )
        invalid = structured_tool_result(invalid_rpc)
        assert invalid["valid"] is False
        assert invalid["executed"] is False
        assert invalid["error"] == {
            "code": "asklens.member.unavailable",
            "message": "A requested query member is unavailable.",
        }
        assert "private_backend_field" not in json.dumps(invalid)
        print("PASS real FastMCP HTTP, server identity, row policy, and safe denial")
    finally:
        request.dispose()


def main() -> None:
    """Run the complete committed reference-demo browser evidence."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with sync_playwright() as playwright:
        verify_browser_and_api(playwright, base_url)
        verify_fastmcp_http(playwright, base_url)

    print("PASS PostgreSQL reference demo Playwright evidence complete")


if __name__ == "__main__":
    main()
