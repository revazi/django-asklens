#!/usr/bin/env python3
"""Capture the seeded offline demo screenshots and 30–60 second browser recording."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from playwright.sync_api import Browser, Page, expect, sync_playwright

PASSWORD = "12admin34"
QUESTION = "Show paid billing revenue by product"
EMPTY_QUESTION = "Show paid billing revenue for the no-sales demo product"


def login(page: Page, base_url: str, username: str) -> None:
    """Use the existing Django admin login form."""

    response = page.goto(f"{base_url}/", wait_until="domcontentloaded")
    assert response is not None and response.status == 200
    expect(page.locator("#id_username")).to_be_visible()
    page.locator("#id_username").fill(username)
    page.locator("#id_password").fill(PASSWORD)
    with page.expect_navigation(wait_until="domcontentloaded") as navigation:
        page.get_by_role("button", name="Log in").click()
    assert navigation.value.status in {200, 403}


def capture_owner_journey(
    browser: Browser,
    base_url: str,
    output_dir: Path,
    video_dir: Path,
) -> None:
    """Record the exact offline scoped success and empty-result journey."""

    context = browser.new_context(
        viewport={"width": 1440, "height": 1200},
        record_video_dir=video_dir,
        record_video_size={"width": 1280, "height": 800},
        color_scheme="light",
    )
    page = context.new_page()
    video = page.video
    started = time.monotonic()
    try:
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_timeout(2_500)
        page.locator("#id_username").fill("facility-owner")
        page.wait_for_timeout(800)
        page.locator("#id_password").fill(PASSWORD)
        page.wait_for_timeout(800)
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("heading", name="AskLens", exact=True)).to_be_visible()
        scope = page.locator('section[aria-label="Tenant row scope"]')
        expect(scope).to_contain_text("North Studio")
        assert "South Studio" not in page.locator("body").inner_text()
        page.wait_for_timeout(3_500)

        page.get_by_role("button", name=QUESTION, exact=True).click()
        expect(page.locator("#question-input")).to_have_value(QUESTION)
        page.wait_for_timeout(1_500)
        page.locator("#send-button").click()
        expect(page.locator("#composer-status")).to_have_text("Done.", timeout=20_000)
        result = page.locator(".result-card").last
        expect(result).to_contain_text("North membership")
        expect(result).to_contain_text("Limit: 10 groups")
        assert "South membership" not in result.inner_text()
        result.scroll_into_view_if_needed()
        page.wait_for_timeout(5_000)
        page.screenshot(path=output_dir / "scoped-revenue.png", full_page=True)
        page.wait_for_timeout(2_500)

        page.get_by_role("button", name=EMPTY_QUESTION, exact=True).click()
        expect(page.locator("#question-input")).to_have_value(EMPTY_QUESTION)
        page.wait_for_timeout(1_500)
        page.locator("#send-button").click()
        expect(page.locator("#composer-status")).to_have_text("Done.", timeout=20_000)
        empty = page.locator(".result-card").last
        expect(empty.get_by_text("No matching rows", exact=True)).to_be_visible()
        empty.scroll_into_view_if_needed()
        page.wait_for_timeout(5_000)

        remaining_ms = max(0, 36_000 - int((time.monotonic() - started) * 1_000))
        page.wait_for_timeout(remaining_ms)
        duration = time.monotonic() - started
        if duration > 60:
            raise RuntimeError(f"Showcase capture exceeded 60 seconds: {duration:.1f}s")
    finally:
        page.close()
        context.close()

    assert video is not None
    recorded_path = Path(video.path())
    shutil.move(recorded_path, output_dir / "offline-demo.webm")


def verify_unmatched_question_error(browser: Browser, base_url: str) -> None:
    """Verify the safe error shown for wording outside exact dummy fixtures."""

    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    try:
        login(page, base_url, "facility-owner")
        page.locator("#question-input").fill("Summarize anything I type")
        page.locator("#send-button").click()
        expect(page.locator("#composer-status")).to_have_text(
            "Request not completed. See the response below.", timeout=20_000
        )
        error = page.locator('.result-card[role="alert"]').last
        expect(error).to_contain_text("AskLens could not complete that request.")
        expect(error).to_contain_text("Choose an exact starter question")
    finally:
        context.close()


def capture_denial(browser: Browser, base_url: str, output_dir: Path) -> None:
    """Capture the opaque host denial without policy or tenant details."""

    context = browser.new_context(
        viewport={"width": 1440, "height": 900}, color_scheme="light"
    )
    page = context.new_page()
    try:
        login(page, base_url, "no-report")
        expect(page.get_by_role("heading", name="Access unavailable")).to_be_visible()
        body = page.locator("body").inner_text()
        for forbidden in ("North Studio", "South Studio", "permission", "tenant"):
            assert forbidden not in body
        page.screenshot(path=output_dir / "neutral-denial.png")
    finally:
        context.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/assets/showcase"))
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir / ".recording"
    shutil.rmtree(video_dir, ignore_errors=True)
    video_dir.mkdir()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                capture_owner_journey(browser, args.base_url, output_dir, video_dir)
                verify_unmatched_question_error(browser, args.base_url)
                capture_denial(browser, args.base_url, output_dir)
            finally:
                browser.close()
    finally:
        shutil.rmtree(video_dir, ignore_errors=True)

    for name in ("scoped-revenue.png", "neutral-denial.png", "offline-demo.webm"):
        path = output_dir / name
        if not path.is_file() or path.stat().st_size < 1_000:
            raise RuntimeError(f"Capture is missing or unexpectedly small: {path}")
    print("PASS login, scoped result, empty result, unmatched error, opaque denial")
    print(f"PASS wrote deterministic offline showcase assets to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
