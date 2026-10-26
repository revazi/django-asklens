#!/usr/bin/env python3
"""Validate links, fragments, navigation, and assets in a MkDocs build."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_NAV_LABELS = {
    "Installation",
    "Core quickstart",
    "Register host models",
    "Providers",
    "Build a custom UI",
    "MCP integration",
    "Security checklist",
}
SHOWCASE_ASSETS = {
    "assets/showcase/scoped-revenue.png",
    "assets/showcase/neutral-denial.png",
    "assets/showcase/offline-demo.webm",
    "assets/showcase/offline-demo.vtt",
}
DRAFT_MARKERS = {
    "awesome-django-submission-packet",
    "django-forum-show-and-tell-draft",
    "django-news-draft",
    "django-packages-observation",
}


class DocumentParser(HTMLParser):
    """Collect links, element IDs, nav labels, and image alternatives."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.ids: set[str] = set()
        self.nav_text: list[str] = []
        self.image_alts: list[str] = []
        self._nav_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if element_id := values.get("id"):
            self.ids.add(element_id)
        if tag in {"a", "link"} and (target := values.get("href")):
            self.links.append(("href", target))
        if tag in {"img", "script", "source", "track", "video"} and (
            target := values.get("src")
        ):
            self.links.append(("src", target))
        if tag == "video" and (poster := values.get("poster")):
            self.links.append(("poster", poster))
        if tag == "img":
            self.image_alts.append(values.get("alt") or "")
        if tag == "nav" or self._nav_depth:
            self._nav_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._nav_depth:
            self._nav_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._nav_depth:
            text = data.strip()
            if text:
                self.nav_text.append(text)


def parse_document(path: Path) -> DocumentParser:
    parser = DocumentParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def local_target(site_dir: Path, source: Path, target: str) -> tuple[Path, str] | None:
    parsed = urlsplit(target)
    if (
        parsed.scheme
        or parsed.netloc
        or target.startswith(("mailto:", "tel:", "data:"))
    ):
        return None
    decoded = unquote(parsed.path)
    if decoded.startswith("/"):
        prefix = "/django-asklens/"
        decoded = decoded.removeprefix(prefix).lstrip("/")
        candidate = site_dir / decoded
    else:
        candidate = source.parent / decoded
    if not decoded:
        candidate = source
    if candidate.is_dir():
        candidate /= "index.html"
    elif not candidate.suffix:
        candidate /= "index.html"
    return candidate.resolve(), unquote(parsed.fragment)


def validate_site(site_dir: Path) -> tuple[list[str], int]:
    """Return final rendered-site failures and the number of HTML pages."""

    site_dir = site_dir.resolve()
    html_paths = sorted(site_dir.rglob("*.html"))
    if not html_paths:
        return [f"No rendered HTML found in {site_dir}"], 0

    documents = {path.resolve(): parse_document(path) for path in html_paths}
    failures: list[str] = []
    for path in site_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(site_dir)
        if (
            "outreach" in relative.parts
            or "__pycache__" in relative.parts
            or path.suffix in {".py", ".pyc"}
        ):
            failures.append(f"internal source/build artifact published: {relative}")

    search_index = site_dir / "search" / "search_index.json"
    if search_index.is_file():
        search_text = search_index.read_text(encoding="utf-8").lower()
        for marker in sorted(DRAFT_MARKERS):
            if marker in search_text:
                failures.append(f"outreach draft found in search index: {marker}")
    for path, document in documents.items():
        for attribute, target in document.links:
            resolved = local_target(site_dir, path, target)
            if resolved is None:
                continue
            target_path, fragment = resolved
            if not target_path.exists():
                relative_source = path.relative_to(site_dir)
                failures.append(f"{relative_source}: broken {attribute} {target}")
                continue
            if fragment and target_path.suffix == ".html":
                target_document = documents.get(target_path)
                if target_document is None:
                    target_document = parse_document(target_path)
                if fragment not in target_document.ids:
                    failures.append(
                        f"{path.relative_to(site_dir)}: missing fragment #{fragment} "
                        f"in {target_path.relative_to(site_dir)}"
                    )

    index = documents.get((site_dir / "index.html").resolve())
    if index is None:
        failures.append("index.html is missing")
    else:
        nav = set(index.nav_text)
        for label in sorted(REQUIRED_NAV_LABELS - nav):
            failures.append(f"index.html: navigation label missing: {label}")

    showcase = documents.get((site_dir / "showcase" / "index.html").resolve())
    if showcase is None:
        failures.append("showcase/index.html is missing")
    elif any(not alt.strip() for alt in showcase.image_alts):
        failures.append("showcase/index.html: every image needs non-empty alt text")

    for relative in SHOWCASE_ASSETS:
        if not (site_dir / relative).is_file():
            failures.append(f"showcase asset missing from built site: {relative}")

    return failures, len(html_paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_dir", nargs="?", default="site", type=Path)
    args = parser.parse_args()
    failures, page_count = validate_site(args.site_dir)
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS rendered docs: {page_count} pages, links, fragments, nav, assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
