"""Version lookup: the repository's VERSION file is the single source of truth."""

from __future__ import annotations

from pathlib import Path


def version_path() -> Path:
    return Path(__file__).resolve().parent.parent / "VERSION"


def version() -> str:
    return version_path().read_text(encoding="utf-8").strip()
