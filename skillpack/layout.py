"""Build-time layout adaptation.

WorkBuddy accepts at most `skill/<dir>/<file>`, so a Python package that lives under a
first-level directory (`scripts/pkg/module.py`) has to be flattened for the package while the
source tree stays untouched. `build_plan` computes that rewrite; nothing is applied to the
source, and any change is reported so the packaged copy is never silently different from the
repository.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

LAYOUTS = ("asis", "workbuddy")
MARKER = "# workbuddy-layout: skill root on sys.path"
BOOTSTRAP_TEMPLATE = """{marker}
import sys as _wb_sys
from pathlib import Path as _wb_path

_SKILL_ROOT = _wb_path(__file__).resolve().parents[{depth}]
if str(_SKILL_ROOT) not in _wb_sys.path:
    _wb_sys.path.insert(0, str(_SKILL_ROOT))
"""


@dataclass
class Plan:
    """Files to rename, packages to lift, and files needing a sys.path bootstrap."""

    layout: str = "asis"
    renames: dict[str, str] = field(default_factory=dict)
    packages: dict[str, str] = field(default_factory=dict)
    patched: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def changes(self) -> bool:
        return bool(self.renames or self.patched)

    def final_paths(self, relative_paths: list[str]) -> list[str]:
        return [self.renames.get(relative, relative) for relative in relative_paths]

    def describe(self) -> str:
        parts = []
        if self.packages:
            parts.append(
                "moved " + ", ".join(f"{old}/ -> {new}/" for old, new in sorted(self.packages.items()))
            )
        if self.patched:
            parts.append("added a sys.path bootstrap to " + ", ".join(sorted(self.patched)))
        return "; ".join(parts)


def _package_dirs(relative_paths: list[str]) -> dict[str, str]:
    """Map `dir/pkg` -> `pkg` for every package that sits one level too deep."""
    path_set = set(relative_paths)
    packages: dict[str, str] = {}
    for relative in relative_paths:
        parts = relative.split("/")
        if len(parts) <= 2:
            continue
        old = f"{parts[0]}/{parts[1]}"
        if f"{old}/__init__.py" in path_set:
            packages[old] = parts[1]
    return packages


def _imports_package(text: str, name: str) -> bool:
    return bool(
        re.search(rf"^[ \t]*(?:from|import)[ \t]+{re.escape(name)}\b", text, re.M)
    )


def _insertion_line(text: str) -> int:
    """0-based line index where a bootstrap may be inserted (after docstring/future imports)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        return max(node.lineno - 1, 0)
    return len(text.splitlines())


def bootstrap_for(depth: int) -> str:
    return BOOTSTRAP_TEMPLATE.format(marker=MARKER, depth=depth)


def patch_source(text: str, depth: int) -> str:
    """Insert the skill-root bootstrap unless the file already carries it."""
    if MARKER in text:
        return text
    lines = text.splitlines(keepends=True)
    index = _insertion_line(text)
    block = bootstrap_for(depth) + "\n"
    head = "".join(lines[:index])
    tail = "".join(lines[index:])
    separator = "" if not head or head.endswith("\n\n") else "\n"
    return f"{head}{separator}{block}{tail}"


def build_plan(relative_paths: list[str], layout: str, reader) -> Plan:
    """Compute the rewrite for `layout`; `reader(relative)` returns the file's text."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout: {layout}")
    plan = Plan(layout=layout)
    if layout == "asis":
        return plan

    path_list = list(relative_paths)
    path_set = set(path_list)
    packages = _package_dirs(path_list)
    if not packages:
        return plan

    root_names = {relative.split("/")[0] for relative in path_list}
    lifted: dict[str, str] = {}
    claimed: dict[str, str] = {}
    for old, new in sorted(packages.items()):
        if new in root_names:
            plan.problems.append(
                f"cannot lift {old}/ to {new}/: the skill root already has an entry named {new}"
            )
            continue
        if new in claimed:
            plan.problems.append(
                f"cannot lift {old}/ and {claimed[new]}/ to the same name {new}/"
            )
            continue
        claimed[new] = old
        lifted[old] = new

    for relative in path_list:
        parts = relative.split("/")
        if len(parts) <= 2:
            continue
        old_package = f"{parts[0]}/{parts[1]}"
        if old_package not in lifted:
            continue
        target = "/".join([lifted[old_package], *parts[2:]])
        if target in path_set:
            plan.problems.append(f"cannot move {relative} to {target}: target already exists")
            continue
        plan.renames[relative] = target

    moved_names = sorted(set(lifted.values()))
    for relative in path_list:
        if relative in plan.renames or not relative.endswith(".py"):
            continue
        depth = relative.count("/")
        if depth > 1:
            continue
        try:
            text = reader(relative)
        except OSError:
            continue
        if not any(_imports_package(text, name) for name in moved_names):
            continue
        plan.patched.append(relative)

    plan.packages = lifted
    return plan
