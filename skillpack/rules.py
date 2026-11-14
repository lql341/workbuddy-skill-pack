"""Packaging rules: what ships, what is stripped, and the structural limits."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from .report import Report

# Cloud upload limit enforced by the skill publishing API (`createSkillCloudUploadSizeError`).
CLOUD_LIMIT_BYTES = 5 * 1024 * 1024
WARN_LIMIT_BYTES = 4 * 1024 * 1024
# The publishing API allows skill/<dir>/<file>; anything nested deeper is rejected with
# "目录层级超限 — Skill 包仅支持两级目录结构（根目录/二级目录/文件）".
MAX_SEGMENTS = 2

EXCLUDED_DIRS = frozenset(
    {
        ".cache",
        ".git",
        ".github",
        ".gitlab",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".vscode",
        "__pycache__",
        "node_modules",
        "test",
        "tests",
    }
)

EXCLUDED_FILE_GLOBS = (
    ".DS_Store",
    ".env",
    ".gitattributes",
    ".gitignore",
    "*.bak",
    "*.key",
    "*.pem",
    "*.pyc",
    "*.slurm",
    "*.swo",
    "*.swp",
    "*~",
    "id_ed25519*",
    "id_rsa*",
)

# Install metadata written by the desktop client; it is regenerated on import.
INSTALL_META_FILES = frozenset(
    {
        "_builtin_market_meta.json",
        "_knot_meta.json",
        "_marketplace_meta.json",
        "_skillhub_meta.json",
        "_user_meta.json",
    }
)

REQUIRED_KEYS = ("name", "description")

# Keys the desktop client reads from SKILL.md frontmatter (`asSkillFrontmatter` plus the
# marketplace fields it passes through).
KNOWN_KEYS = (
    "allowed-tools",
    "description",
    "description_en",
    "description_zh",
    "disable",
    "disable-model-invocation",
    "displayName",
    "display_name",
    "display_name_en",
    "examples_en",
    "examples_zh",
    "homepage",
    "license",
    "name",
    "slug",
    "summary",
    "tag_en",
    "tag_zh",
    "tags_en",
    "tags_zh",
    "user-invocable",
    "version",
    "when-to-use",
)


def is_excluded_file(name: str, keep_patterns: tuple[str, ...]) -> bool:
    if any(fnmatch.fnmatch(name, pattern) for pattern in keep_patterns):
        return False
    if name in INSTALL_META_FILES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_FILE_GLOBS)


def iter_files(
    root: Path, keep: tuple[str, ...], extra_excludes: tuple[str, ...]
) -> Iterator[tuple[str, Path]]:
    """Yield (path relative to the skill root, source path) for packable files."""
    for current, dirnames, filenames in os.walk(root):
        rel_dir = Path(current).relative_to(root)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in EXCLUDED_DIRS
            and not any(fnmatch.fnmatch(name, pattern) for pattern in extra_excludes)
            and not (Path(current) / name).is_symlink()
        )
        for filename in sorted(filenames):
            source = Path(current) / filename
            relative = (rel_dir / filename).as_posix()
            if source.is_symlink():
                continue
            if is_excluded_file(filename, keep):
                continue
            if any(fnmatch.fnmatch(relative, pattern) for pattern in extra_excludes):
                continue
            yield relative, source


def check_depth(relative_paths: list[str], report: Report) -> None:
    """Fail when any path is nested deeper than skill/<dir>/<file>."""
    offenders = [
        (len([part for part in relative.split("/") if part]), relative)
        for relative in relative_paths
        if len([part for part in relative.split("/") if part]) > MAX_SEGMENTS
    ]
    if not offenders:
        return
    offenders.sort(reverse=True)
    detail = ", ".join(f"{path} ({depth} segments)" for depth, path in offenders[:8])
    extra = "" if len(offenders) <= 8 else f", ... +{len(offenders) - 8} more"
    report.error(
        "目录层级超限 / directory depth exceeded: a skill package allows at most "
        f"skill/<dir>/<file>. Offending paths: {detail}{extra}"
    )
    report.info["depth_offenders"] = [path for _, path in offenders]
