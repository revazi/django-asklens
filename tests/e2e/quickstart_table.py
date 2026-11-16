"""Offline Chromium DOM regression for the source-only minimal table consumer.

Default: actual template/JS with intercepted synthetic HTTP. Optional
--base-url: an owned local installed-candidate Django test server. Neither is
production authentication/wire acceptance or MCP transport evidence. Run with
the dev interpreter after installing Chromium.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples/quickstart/shop"
ORIGIN = "https://asklens.invalid"


def main():
    template = (EXAMPLE / "templates/shop/table.html").read_text()
    template = (
        template.replace("{% load static %}", "")
        .replace("{% static 'shop/table.js' %}", "/table.js")
        .replace(
            "{% csrf_token %}",
            '<input type="hidden" name="csrfmiddlewaretoken" value="synthetic-csrf">',
        )
    )
    script = (EXAMPLE / "static/shop/table.js").read_text()
    result = {
        "columns": [
            {"key": "product", "label": "Product", "type": "string", "nullable": False},
            {
                "key": "total_cents",
                "label": "Total (cents)",
                "type": "integer",
                "nullable": False,
            },
        ],
        "data": [
            {"product": "North class", "total_cents": 2000},
            {"product": "North membership", "total_cents": 1200},
        ],
        "row_count": 2,
        "result_metadata": {"truncated": False},
    }
    answer = {
        "status": 200,
        "content_type": "application/json",
        "body": json.dumps(
            {
                "response_type": "query",
                "result": result,
            }
        ),
    }
    requests = []

    def route_request(route):
        if route.request.url == ORIGIN + "/":
            route.fulfill(status=200, content_type="text/html", body=template)
        elif route.request.url == ORIGIN + "/table.js":
            route.fulfill(status=200, content_type="text/javascript", body=script)
        elif route.request.url == ORIGIN + "/asklens/query/":
            requests.append(route.request)
            route.fulfill(**answer)
        else:
            raise AssertionError("Unexpected browser request; network is forbidden")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            context.add_cookies(
                [{"name": "sessionid", "value": "synthetic-session", "url": ORIGIN}]
            )
            context.route("**/*", route_request)
            page = context.new_page()
            page.goto(ORIGIN)
            question = page.get_by_label("Question", exact=True)
            button = page.get_by_role("button", name="Ask", exact=True)
            status = page.get_by_role("status")
            question.focus()
            question.press("Enter")
            expect(status).to_have_text("2 rows returned.")
            expect(page.get_by_role("table")).to_have_count(1)
            expect(page.get_by_role("caption")).to_have_text(
                "Orders in your current authorized scope"
            )
            expect(page.locator('th[scope="col"]')).to_have_count(2)
            expect(page.locator("tbody tr")).to_have_count(2)
            request = requests[-1]
            assert request.method == "POST"
            assert request.post_data_json == {
                "question": "Show my paid orders",
                "include_presentation": False,
            }
            assert request.headers["x-csrftoken"] == "synthetic-csrf"
            assert "sessionid=synthetic-session" in request.headers["cookie"]

            # Labels/values are text, extra keys stay hidden, decimals stay exact.
            hostile = '<img src=x onerror="window.__asklensXss=true">'
            result["columns"][0]["label"] = hostile
            result["data"] = [
                {
                    "product": hostile,
                    "total_cents": "9007199254740993.01",
                    "hidden": "do-not-render",
                }
            ]
            result["row_count"] = 1
            result["result_metadata"]["truncated"] = True
            answer["body"] = json.dumps({"response_type": "query", "result": result})
            button.click()
            expect(status).to_contain_text("Showing a limited result")
            expect(page.locator("tbody td").nth(0)).to_have_text(hostile)
            expect(page.locator("tbody td").nth(1)).to_have_text("9007199254740993.01")
            expect(page.locator("#results img")).to_have_count(0)
            assert "do-not-render" not in page.locator("#results").inner_text()
            assert page.evaluate("window.__asklensXss") is None

            result["data"] = []
            result["row_count"] = 0
            result["result_metadata"]["truncated"] = False
            answer["body"] = json.dumps({"response_type": "query", "result": result})
            question.fill("Show my refunded orders")
            button.click()
            expect(status).to_have_text(
                "No matching rows in your current authorized scope."
            )
            expect(page.locator("tbody tr")).to_have_count(0)

            for code, content_type, body, message in (
                (
                    400,
                    "application/json",
                    json.dumps(
                        {
                            "error": {
                                "code": "asklens.member.unavailable",
                                "message": "never-display-raw",
                            }
                        }
                    ),
                    "A requested query member is unavailable.",
                ),
                (403, "text/html", "never-display-raw", "Access failed."),
                (429, "application/json", "{}", "Too many requests."),
                (
                    500,
                    "text/html",
                    "never-display-raw",
                    "The request could not be completed.",
                ),
                (
                    200,
                    "application/json",
                    '{"response_type":"query","result":{}}',
                    "The request could not be completed.",
                ),
                (
                    200,
                    "application/json",
                    '{"response_type":"capabilities"}',
                    "Use one of the exact configured data questions.",
                ),
            ):
                answer.update(status=code, content_type=content_type, body=body)
                button.click()
                expect(status).to_contain_text(message)
                expect(page.locator("#results table")).to_have_count(0)
                expect(button).to_be_enabled()
                expect(page.locator("#results")).to_have_attribute("aria-busy", "false")
                assert "never-display-raw" not in page.locator("main").inner_text()

            # Hold a synthetic response to observe the accessible loading state.
            context.unroute("**/*", route_request)
            pending = []

            def hold_local_response(route):
                if route.request.url != ORIGIN + "/asklens/query/":
                    raise AssertionError("Unexpected browser request forbidden")
                pending.append(route)

            context.route("**/*", hold_local_response)
            button.click()
            expect(button).to_be_disabled()
            expect(status).to_have_text("Loading…")
            expect(page.locator("#results")).to_have_attribute("aria-busy", "true")
            assert len(pending) == 1
            pending.pop().abort("failed")
            expect(button).to_be_enabled()
            expect(status).to_contain_text("Check your connection and sign in")
            print(
                "PASS minimal consumer: safe DOM, keyboard, empty/limited/denied, "
                "CSRF/session request, loading and recovery "
                "(synthetic intercepted HTTP)"
            )
        finally:
            browser.close()


def verify_installed_server(base_url):
    """Real local HTTP against the copied host in the candidate API environment.

    The server/test database belongs to Django's StaticLiveServerTestCase. This
    process supplies only the browser driver; it never imports AskLens/source.
    """
    url = urlsplit(base_url)
    assert url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}
    assert url.port and not url.path and not url.query and not url.fragment
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for username, permitted in (
                ("asklens-alice", True),
                ("asklens-no-report", False),
            ):
                context = browser.new_context()

                def only_local(route):
                    if not route.request.url.startswith(base_url + "/"):
                        raise AssertionError("Nonlocal browser request forbidden")
                    route.continue_()

                context.route("**/*", only_local)
                page = context.new_page()
                page.goto(base_url + "/table/")
                expect(page.get_by_role("heading", name="Host sign in")).to_be_visible()
                page.get_by_label("Username").fill(username)
                page.get_by_label("Password").fill("synthetic-recipe-test-only")
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(
                    page.get_by_role("heading", name="My orders", exact=True)
                ).to_be_visible()
                expect(
                    page.locator('script[src="/static/shop/table.js"]')
                ).to_have_count(1)
                status = page.get_by_role("status")
                button = page.get_by_role("button", name="Ask", exact=True)

                def ask(question, page=page, button=button):
                    page.get_by_label("Question", exact=True).fill(question)
                    with page.expect_response(base_url + "/asklens/query/") as received:
                        button.click()
                    response = received.value
                    assert response.request.headers.get("x-csrftoken")
                    assert response.request.post_data_json == {
                        "question": question,
                        "include_presentation": False,
                    }
                    return response

                # Authenticated sessions still require CSRF on unsafe requests.
                missing_csrf = context.request.post(
                    base_url + "/asklens/query/",
                    data={"question": "Show my paid orders"},
                )
                assert missing_csrf.status == 403
                assert (
                    missing_csrf.json()["error"]["code"]
                    == "asklens.authorization.denied"
                )
                response = ask("Show my paid orders")
                if permitted:
                    assert response.status == 200
                    expect(status).to_have_text("2 rows returned.")
                    expect(page.locator("tbody tr")).to_have_count(2)
                    expect(page.locator("tbody")).to_contain_text("North class")
                    assert (
                        "South membership" not in page.locator("#results").inner_text()
                    )
                    empty = ask("Show my refunded orders")
                    assert empty.status == 200
                    expect(status).to_have_text(
                        "No matching rows in your current authorized scope."
                    )
                    expect(page.locator("tbody tr")).to_have_count(0)
                else:
                    assert response.status == 400
                    assert (
                        response.json()["error"]["code"] == "asklens.member.unavailable"
                    )
                    expect(status).to_contain_text(
                        "A requested query member is unavailable."
                    )
                    expect(page.locator("#results table")).to_have_count(0)
                    assert context.request.get(
                        base_url + "/asklens/catalog/"
                    ).json() == {"resources": []}
                expect(button).to_be_enabled()
                context.close()
            print(
                "PASS installed-server browser: login/session/CSRF, static UI, "
                "scoped table/empty/opaque denial (local synthetic HTTP only)"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Owned local candidate test server only")
    arguments = parser.parse_args()
    if arguments.base_url:
        verify_installed_server(arguments.base_url)
    else:
        main()
