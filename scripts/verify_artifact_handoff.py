"""Fail closed unless downloaded release artifacts match the build outputs."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
from pathlib import Path

HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"[0-9]+(?:[A-Za-z0-9.!+_-]*[A-Za-z0-9])?")


class ArtifactHandoffError(ValueError):
    """The downloaded artifacts are not the exact files built for the release."""


def _validated(value: str, pattern: re.Pattern[str], label: str) -> str:
    if pattern.fullmatch(value) is None:
        raise ArtifactHandoffError(f"Invalid {label}.")
    return value


def _sha256_regular_file(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ArtifactHandoffError(
            "Unable to open a release artifact safely."
        ) from None

    try:
        with os.fdopen(descriptor, "rb") as artifact:
            if not stat.S_ISREG(os.fstat(artifact.fileno()).st_mode):
                raise ArtifactHandoffError(
                    "Release artifacts must be regular non-symlink files."
                )
            digest = hashlib.sha256()
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise ArtifactHandoffError(
            "Unable to read a release artifact safely."
        ) from None
    return digest.hexdigest()


def verify_artifacts(
    artifact_dir: Path,
    version: str,
    wheel_sha256: str,
    sdist_sha256: str,
) -> None:
    """Authenticate the exact top-level wheel and sdist in ``artifact_dir``."""

    version = _validated(version, VERSION, "version")
    wheel_sha256 = _validated(wheel_sha256, HEX_SHA256, "wheel SHA-256")
    sdist_sha256 = _validated(sdist_sha256, HEX_SHA256, "sdist SHA-256")

    wheel_name = f"django_asklens-{version}-py3-none-any.whl"
    sdist_name = f"django_asklens-{version}.tar.gz"
    expected = {
        wheel_name: wheel_sha256,
        sdist_name: sdist_sha256,
    }

    try:
        if not stat.S_ISDIR(artifact_dir.lstat().st_mode):
            raise ArtifactHandoffError(
                "Artifact directory must be a real directory, not a symlink."
            )
        entries = list(os.scandir(artifact_dir))
    except ArtifactHandoffError:
        raise
    except OSError:
        raise ArtifactHandoffError(
            "Artifact directory is missing or unreadable."
        ) from None

    if len(entries) != len(expected) or {entry.name for entry in entries} != set(
        expected
    ):
        raise ArtifactHandoffError(
            "Artifact directory must contain exactly the expected wheel and sdist."
        )

    entries_by_name = {entry.name: entry for entry in entries}
    for filename, expected_digest in expected.items():
        entry = entries_by_name[filename]
        try:
            entry_status = entry.stat(follow_symlinks=False)
            is_symlink = entry.is_symlink()
        except OSError:
            raise ArtifactHandoffError(
                "Unable to inspect a release artifact safely."
            ) from None
        if is_symlink or not stat.S_ISREG(entry_status.st_mode):
            raise ArtifactHandoffError(
                "Release artifacts must be regular non-symlink files."
            )
        if _sha256_regular_file(artifact_dir / filename) != expected_digest:
            artifact_type = "wheel" if filename == wheel_name else "sdist"
            raise ArtifactHandoffError(
                f"Downloaded {artifact_type} digest did not match the build output."
            )


def main() -> None:
    """Validate command-line inputs and the downloaded artifact handoff."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--sdist-sha256", required=True)
    arguments = parser.parse_args()

    try:
        verify_artifacts(
            arguments.artifact_dir,
            arguments.version,
            arguments.wheel_sha256,
            arguments.sdist_sha256,
        )
    except ArtifactHandoffError as error:
        raise SystemExit(f"Artifact handoff verification failed: {error}") from None
    print("PASS authenticated the exact wheel and sdist artifact handoff")


if __name__ == "__main__":
    main()
