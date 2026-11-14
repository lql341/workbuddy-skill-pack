"""SKILL.md frontmatter reading.

`pyyaml` is used when available so real YAML is honoured exactly; otherwise a minimal
subset parser handles the scalar and dash-list forms used by agent skills.
"""

from __future__ import annotations

import re

from .report import Report

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)
MINIMAL_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$")
MINIMAL_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")


def unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_minimal(raw: str) -> dict:
    """Parse the YAML subset used by skill frontmatter: scalars and dash lists."""
    data: dict[str, object] = {}
    current: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = MINIMAL_ITEM_RE.match(line)
        if item and current:
            bucket = data.get(current)
            if isinstance(bucket, list):
                bucket.append(unquote(item.group(1)))
            continue
        pair = MINIMAL_KEY_RE.match(line)
        if not pair:
            continue
        key, value = pair.group(1), pair.group(2).strip()
        current = key
        data[key] = [] if value == "" else unquote(value)
    return data


def parse_frontmatter(text: str) -> tuple[dict, str] | tuple[None, None]:
    """Split a SKILL.md into (minimal-parsed frontmatter, body)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None
    return parse_minimal(match.group(1)), text[match.end() :]


def load_frontmatter(text: str, report: Report) -> tuple[dict | None, str | None]:
    """Split a SKILL.md into (frontmatter, body), reporting parse problems."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None
    body = text[match.end() :]
    try:
        import yaml  # type: ignore
    except ImportError:
        report.warn("pyyaml not installed; used the built-in minimal frontmatter parser")
        return parse_minimal(match.group(1)), body
    try:
        data = yaml.safe_load(match.group(1))
    except Exception as exc:  # noqa: BLE001 - surface the parser message verbatim
        report.error(f"SKILL.md frontmatter is not valid YAML: {exc}")
        return None, body
    if not isinstance(data, dict):
        report.error("SKILL.md frontmatter must be a mapping")
        return None, body
    return data, body
