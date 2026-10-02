"""Download and authenticate one django-asklens release from PyPI.

The caller supplies digests obtained independently from the artifacts being
fetched (for example, from the release build job). PyPI's JSON metadata is used
only to locate the two files and is checked against those caller-supplied
values before and after download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = "django-asklens"
JSON_URL = "https://pypi.org/pypi/django-asklens/{version}/json"
ALLOWED_FILE_HOST = "files.pythonhosted.org"
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"[0-9]+(?:[A-Za-z0-9.!+_-]*[A-Za-z0-9])?")


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a local file."""

    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_cli_value(value: str, pattern: re.Pattern[str], label: str) -> str:
    """Reject values that are unsafe or ambiguous in a release request."""

    if pattern.fullmatch(value) is None:
        raise SystemExit(f"Invalid {label}.")
    return value


def fetch_json(url: str) -> dict:
    """Fetch a bounded JSON object from the fixed PyPI API."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "django-asklens-published-artifact-verifier/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            final_url = urllib.parse.urlsplit(response.geturl())
            if final_url.scheme != "https" or final_url.hostname != "pypi.org":
                raise SystemExit("PyPI metadata redirected outside the fixed host.")
            payload = response.read(MAX_ARTIFACT_BYTES + 1)
    except (OSError, urllib.error.URLError):
        raise SystemExit("Unable to retrieve PyPI release metadata.") from None
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise SystemExit("PyPI metadata exceeded the verifier size limit.")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit("PyPI returned invalid release metadata.") from None
    if not isinstance(document, dict):
        raise SystemExit("PyPI returned invalid release metadata.")
    return document


def download(url: str, destination: Path) -> None:
    """Download one bounded artifact without following it into the checkout."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "django-asklens-published-artifact-verifier/1"},
    )
    temporary = destination.with_suffix(destination.suffix + ".part")
    total = 0
    try:
        try:
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                temporary.open("wb") as output,
            ):
                final_url = urllib.parse.urlsplit(response.geturl())
                if (
                    final_url.scheme != "https"
                    or final_url.hostname != ALLOWED_FILE_HOST
                    or Path(urllib.parse.unquote(final_url.path)).name
                    != destination.name
                ):
                    raise SystemExit(
                        "PyPI artifact redirected outside the fixed file host."
                    )
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARTIFACT_BYTES:
                        raise SystemExit(
                            "PyPI artifact exceeded the verifier size limit."
                        )
                    output.write(chunk)
            temporary.replace(destination)
        except (OSError, urllib.error.URLError):
            raise SystemExit("Unable to retrieve a PyPI release artifact.") from None
    finally:
        temporary.unlink(missing_ok=True)


def select_artifacts(document: dict, version: str) -> dict[str, dict]:
    """Select exactly one non-yanked universal wheel and one source archive."""

    info = document.get("info")
    urls = document.get("urls")
    if not isinstance(info, dict) or not isinstance(urls, list):
        raise SystemExit("PyPI release metadata is missing required fields.")
    if info.get("name") != PROJECT or info.get("version") != version:
        raise SystemExit("PyPI release metadata did not match the requested project.")

    selected: dict[str, dict] = {}
    for entry in urls:
        if not isinstance(entry, dict):
            continue
        package_type = entry.get("packagetype")
        if package_type not in {"bdist_wheel", "sdist"}:
            continue
        if package_type in selected:
            raise SystemExit(f"PyPI returned multiple {package_type} artifacts.")
        if entry.get("yanked") is not False:
            raise SystemExit("Refusing to verify a yanked release artifact.")
        selected[package_type] = entry

    if set(selected) != {"bdist_wheel", "sdist"}:
        raise SystemExit("Expected exactly one wheel and one source distribution.")
    wheel_name = selected["bdist_wheel"].get("filename")
    sdist_name = selected["sdist"].get("filename")
    if wheel_name != f"django_asklens-{version}-py3-none-any.whl":
        raise SystemExit("PyPI wheel filename did not match the requested release.")
    if sdist_name != f"django_asklens-{version}.tar.gz":
        raise SystemExit("PyPI source filename did not match the requested release.")
    return selected


def main() -> None:
    """Download the requested wheel and sdist after exact digest validation."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--sdist-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    version = validate_cli_value(arguments.version, VERSION, "version")
    expected = {
        "bdist_wheel": validate_cli_value(
            arguments.wheel_sha256, HEX_SHA256, "wheel SHA-256"
        ),
        "sdist": validate_cli_value(
            arguments.sdist_sha256, HEX_SHA256, "sdist SHA-256"
        ),
    }
    output_dir = arguments.output_dir.resolve()
    if not output_dir.is_dir() or any(output_dir.iterdir()):
        raise SystemExit("Output directory must exist and be empty.")

    document = fetch_json(JSON_URL.format(version=version))
    selected = select_artifacts(document, version)
    for package_type, entry in selected.items():
        filename = entry["filename"]
        url = entry.get("url")
        digests = entry.get("digests")
        parsed_url = urllib.parse.urlsplit(url if isinstance(url, str) else "")
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != ALLOWED_FILE_HOST
            or Path(urllib.parse.unquote(parsed_url.path)).name != filename
        ):
            raise SystemExit("PyPI artifact URL failed the fixed-host filename check.")
        if (
            not isinstance(digests, dict)
            or digests.get("sha256") != expected[package_type]
        ):
            raise SystemExit("PyPI metadata digest did not match the expected digest.")

        destination = output_dir / filename
        download(url, destination)
        if sha256(destination) != expected[package_type]:
            destination.unlink(missing_ok=True)
            raise SystemExit(
                "Downloaded artifact digest did not match the expected digest."
            )
        print(f"PASS authenticated downloaded {package_type}: {filename}")


if __name__ == "__main__":
    main()
