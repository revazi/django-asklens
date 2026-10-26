"""Small build-only adaptations for Markdown that also renders on GitHub."""

from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath

REPOSITORY_SOURCE = "https://github.com/revazi/django-asklens"
CALLOUT = re.compile(
    r"^> \[!(?P<kind>NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\n"
    r"(?P<body>(?:^>.*(?:\n|$))*)",
    re.MULTILINE,
)
REPOSITORY_LINK = re.compile(
    r"(?P<prefix>!?\[[^\]]*\]\()(?P<target>\.\./[^)\s]+)(?P<suffix>\))"
)
SHOWCASE_MEDIA = re.compile(
    r'(?P<prefix>(?:src|href|poster)=")'
    r"(?:assets/showcase/|https://raw\.githubusercontent\.com/"
    r"revazi/django-asklens/main/docs/assets/showcase/)"
    r'(?P<name>[^"/]+)(?P<suffix>")'
)
SHOWCASE_MARKDOWN_MEDIA = re.compile(
    r"(?P<prefix>!?\[[^\]]*\]\()"
    r"https://raw\.githubusercontent\.com/revazi/django-asklens/"
    r"main/docs/assets/showcase/(?P<name>[^)\s]+)(?P<suffix>\))"
)


def _render_callout(match: re.Match[str]) -> str:
    """Translate one GitHub callout to the built-in MkDocs admonition syntax."""

    kind = match.group("kind").lower()
    body = "\n".join(
        f"    {line[2:] if line.startswith('> ') else line[1:]}"
        for line in match.group("body").splitlines()
    )
    return f'!!! {kind} "{match.group("kind").title()}"\n{body}\n'


def _repository_url(page_path: str, target: str) -> str:
    """Resolve a repository-relative target to its source browser URL."""

    path, separator, fragment = target.partition("#")
    resolved = posixpath.normpath(str(PurePosixPath("docs", page_path).parent / path))
    view = "tree" if path.endswith("/") else "blob"
    url = f"{REPOSITORY_SOURCE}/{view}/main/{resolved}"
    return f"{url}#{fragment}" if separator else url


def on_page_markdown(markdown: str, *, page, **kwargs) -> str:  # noqa: ANN001
    """Keep source-friendly callouts and repository links usable in the site."""

    del kwargs
    markdown = CALLOUT.sub(_render_callout, markdown)
    markdown = REPOSITORY_LINK.sub(
        lambda match: (
            f"{match.group('prefix')}"
            f"{_repository_url(page.file.src_path, match.group('target'))}"
            f"{match.group('suffix')}"
        ),
        markdown,
    )
    markdown = SHOWCASE_MARKDOWN_MEDIA.sub(
        r"\g<prefix>assets/showcase/\g<name>\g<suffix>", markdown
    )
    if page.file.src_path == "showcase.md":
        markdown = SHOWCASE_MEDIA.sub(
            r"\g<prefix>../assets/showcase/\g<name>\g<suffix>", markdown
        )
    return markdown
