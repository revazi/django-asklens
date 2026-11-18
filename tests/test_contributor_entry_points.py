"""Offline checks of the supported GitHub form subset and contributor navigation.

PyYAML is already present in the locked dev graph via the optional MCP tooling.
These checks do not submit issues or claim hosted GitHub form-rendering evidence.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
FORMS = {
    "bug_report.yml": "bug",
    "integration_friction.yml": "question",
    "provider_compatibility.yml": "question",
}
COMMON_FIELDS = {
    "public-safety",
    "artifact",
    "platform",
    "expected",
    "actual",
    "reproduction",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject YAML keys that would otherwise silently overwrite evidence fields."""

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        assert len(keys) == len(set(keys)), "Duplicate YAML key"
        return super().construct_mapping(node, deep=deep)


def load_yaml(path: Path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


@pytest.mark.parametrize("filename", FORMS)
def test_forms_require_safe_reproducible_evidence(filename: str) -> None:
    form = load_yaml(TEMPLATES / filename)
    assert set(form) == {"name", "description", "title", "labels", "body"}
    assert all(
        isinstance(form[key], str) and form[key].strip()
        for key in ("name", "description", "title")
    )
    assert form["labels"] == [FORMS[filename]]  # Existing labels; no new taxonomy.
    notice, *fields = form["body"]
    assert set(notice) == {"type", "attributes"}
    assert notice["type"] == "markdown"
    assert set(notice["attributes"]) == {"value"}
    warning = notice["attributes"]["value"]
    for required in (
        "no secrets or customer data",
        ".env",
        "private endpoints",
        "raw provider",
        "Do not post it here",
        "/security/policy",
    ):
        assert required in warning

    ids = [field["id"] for field in fields]
    assert len(ids) == len(set(ids))
    expected = COMMON_FIELDS | (
        {"provider"} if filename == "provider_compatibility.yml" else set()
    )
    assert set(ids) == expected
    for field in fields:
        assert re.fullmatch(r"[a-z][a-z0-9-]*", field["id"])
        attributes = field["attributes"]
        assert isinstance(attributes["label"], str) and attributes["label"].strip()
        if field["id"] == "public-safety":
            assert set(field) == {"type", "id", "attributes"}
            assert field["type"] == "checkboxes"
            assert set(attributes) == {"label", "options"}
            [option] = attributes["options"]
            assert set(option) == {"label", "required"}
            assert option["required"] is True
            assert "synthetic data only" in option["label"]
            assert "no secrets or customer data" in option["label"]
        else:
            assert set(field) == {"type", "id", "attributes", "validations"}
            assert field["type"] == "textarea"
            assert set(attributes) == {"label", "description"}
            assert (
                isinstance(attributes["description"], str)
                and attributes["description"].strip()
            )
            assert field["validations"] == {"required": True}

    by_id = {field["id"]: field["attributes"] for field in fields}
    for token in ("version", "commit SHA", "SHA-256", "public artifact"):
        assert token in by_id["artifact"]["description"]
    for token in ("OS/architecture", "Python", "Django", "Pydantic"):
        assert token in by_id["platform"]["description"]
    assert "synthetic" in by_id["reproduction"]["description"]
    assert "offline" in by_id["reproduction"]["description"]
    if "provider" in by_id:
        assert "model/snapshot" in by_id["provider"]["description"]
        assert "observation date" in by_id["provider"]["description"]
        assert "Mocks and schema inspection" in warning
        assert "No live request or spend is required" in warning


def test_config_routes_features_support_and_security_without_discussions() -> None:
    assert {path.name for path in TEMPLATES.glob("*.yml")} == set(FORMS) | {
        "config.yml"
    }
    config = load_yaml(TEMPLATES / "config.yml")
    assert set(config) == {"blank_issues_enabled", "contact_links"}
    assert config["blank_issues_enabled"] is False
    links = config["contact_links"]
    assert len(links) == 3
    for link in links:
        assert set(link) == {"name", "url", "about"}
        assert all(isinstance(value, str) and value.strip() for value in link.values())
        assert "/discussions" not in link["url"]
    assert {urlsplit(link["url"]).fragment for link in links} == {
        "feature-requests",
        "support-questions",
        "",
    }
    assert (
        links[-1]["url"] == "https://github.com/revazi/django-asklens/security/policy"
    )
    assert "if enabled" in links[-1]["about"]


def assert_repository_target(source: Path, target: str) -> None:
    """Resolve source links offline, including repository links used by forms."""
    parsed = urlsplit(target)
    path = unquote(parsed.path)
    if parsed.netloc:
        if parsed.netloc != "github.com" or not path.startswith(
            "/revazi/django-asklens/"
        ):
            # External documentation is checked separately, never fetched by pytest.
            return
        relative = path.removeprefix("/revazi/django-asklens/")
        if relative.startswith("blob/main/"):
            destination = ROOT / relative.removeprefix("blob/main/")
        elif relative == "security/policy":
            destination = ROOT / "SECURITY.md"
        elif relative == "issues/new":
            query = parse_qs(parsed.query)
            if "template" in query:
                assert query["template"][0] in FORMS
            if "labels" in query:
                assert query["labels"][0] in {"enhancement", "question"}
            return
        else:
            assert re.fullmatch(r"issues(?:/new/choose|/\d+)?|pull/\d+", relative), (
                target
            )
            return  # Issue/PR existence is checked manually, not by this offline test.
    else:
        destination = (source.parent / path).resolve() if path else source
    assert destination.is_relative_to(ROOT), target
    assert destination.is_file(), target
    if parsed.fragment:
        headings = re.findall(r"^#{1,6} (.+)$", destination.read_text(), re.MULTILINE)
        anchors = {
            re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
            for heading in headings
        }
        assert unquote(parsed.fragment) in anchors, target


@pytest.mark.parametrize(
    "target",
    [
        "missing-contributor-guide.md",
        "#nonexistent-heading",
        "https://github.com/revazi/django-asklens/issues/new?template=missing.yml",
        "https://github.com/revazi/django-asklens/issues/new?labels=unknown-label",
        "https://github.com/revazi/django-asklens/discussions",
    ],
)
def test_broken_repository_links_are_rejected(target: str) -> None:
    with pytest.raises(AssertionError):
        assert_repository_target(ROOT / "CONTRIBUTING.md", target)


def test_duplicate_yaml_keys_are_rejected() -> None:
    with pytest.raises(AssertionError, match="Duplicate YAML key"):
        yaml.load("required: true\nrequired: false\n", Loader=UniqueKeyLoader)


def test_contributor_links_and_form_routes_resolve_in_source() -> None:
    for source in (
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs/contributing.md",
        *(TEMPLATES / name for name in FORMS),
    ):
        for target in MARKDOWN_LINK.findall(source.read_text(encoding="utf-8")):
            assert_repository_target(source, target)
    for link in load_yaml(TEMPLATES / "config.yml")["contact_links"]:
        assert_repository_target(TEMPLATES / "config.yml", link["url"])


def test_docs_navigation_exposes_contributor_hub_and_honest_task_status() -> None:
    for path in ("README.md", "docs/index.md", "mkdocs.yml"):
        assert "contributing.md" in (ROOT / path).read_text(encoding="utf-8")
    guide = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "uv sync --locked --group dev" in guide
    assert "uv run --no-sync pytest tests/test_scaffold.py" in guide
    assert "DJANGO_ASKLENS_LIVE_LLM=0" in guide
    assert "DJANGO_ASKLENS_DEMO_LIVE_LLM=0" in guide
    assert "Independent review and hosted checks are required" in guide
    hub = (ROOT / "docs/contributing.md").read_text(encoding="utf-8")
    assert "no currently available, fully scoped `good first issue`" in hub
    assert "not advertised as still-open assignments" in hub
    assert "No additional typing task was confirmed" in hub
    roadmap = (ROOT / "docs/maintenance-roadmap.md").read_text(encoding="utf-8")
    assert "00dd48cca9244ca8d0b4e059fcbf0380aba3374a" in roadmap
    assert "Keep [#189]" not in roadmap
