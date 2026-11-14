"""Source validation, zip building, and post-build verification."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .frontmatter import load_frontmatter
from .layout import Plan, build_plan, patch_source
from .report import Report
from .rules import (
    CLOUD_LIMIT_BYTES,
    INSTALL_META_FILES,
    KNOWN_KEYS,
    REQUIRED_KEYS,
    WARN_LIMIT_BYTES,
    check_depth,
    iter_files,
)

SLUG_RE = re.compile(r"[A-Za-z0-9._-]+")
MIN_LINES = 12


def _require_skill_md(source: Path, report: Report) -> Path | None:
    skill_md = source / "SKILL.md"
    if not skill_md.is_file():
        report.error(f"SKILL.md not found at {skill_md}")
        return None
    return skill_md


def _collect(
    source: Path, keep: tuple[str, ...], extra_excludes: tuple[str, ...]
) -> list[tuple[str, Path]]:
    return list(iter_files(source, keep, extra_excludes))


def _plan(source: Path, files: list[tuple[str, Path]], layout: str, report: Report) -> Plan:
    paths = [relative for relative, _ in files]
    sources = {relative: path for relative, path in files}

    def reader(relative: str) -> str:
        return sources[relative].read_text(encoding="utf-8")

    try:
        plan = build_plan(paths, layout, reader)
    except ValueError as exc:
        report.error(str(exc))
        return Plan(layout=layout)
    for problem in plan.problems:
        report.error(f"layout {layout}: {problem}")
    report.info["layout"] = plan.layout
    if plan.changes:
        report.info["layout_changes"] = plan.describe()
        if "layout-warned" not in report.flags:
            report.flags.add("layout-warned")
            report.warn(
                "packaged copy differs from the source tree: "
                f"{plan.describe()} — run the extracted code before publishing"
            )
    return plan


def validate_source(
    source: Path,
    keep: tuple[str, ...],
    extra_excludes: tuple[str, ...],
    report: Report,
    layout: str = "asis",
) -> None:
    """Check a skill directory against every packaging rule."""
    skill_md = _require_skill_md(source, report)
    if skill_md is None:
        return
    text = skill_md.read_text(encoding="utf-8")
    data, body = load_frontmatter(text, report)
    if data is None:
        if not report.errors:
            report.error("SKILL.md has no YAML frontmatter (--- ... ---)")
        return

    for key in REQUIRED_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            report.error(f'SKILL.md format is incorrect. Required field "{key}" is missing.')
        elif "\n" in value:
            report.warn(f"{key} spans multiple lines; keep it a single line")

    name = data.get("name")
    if isinstance(name, str) and name.strip():
        if not SLUG_RE.fullmatch(name.strip()):
            report.warn(f"name {name!r} is not a slug (a-z0-9._-); some listings reject it")
        if name.strip() != source.name:
            report.warn(
                f"folder name {source.name!r} differs from frontmatter name {name.strip()!r}; "
                "the zip and the installed folder use the frontmatter name"
            )

    if not body or not body.strip():
        report.warn("SKILL.md body is empty; instructions belong after the frontmatter")
    elif len([line for line in text.splitlines() if line.strip()]) < MIN_LINES:
        report.warn("SKILL.md looks very short; verify the instructions are complete")

    for key in ("examples_zh", "examples_en"):
        value = data.get(key)
        if value is None:
            continue
        if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            report.error(f"{key} must be a YAML list of strings")
        elif len(value) > 3:
            report.warn(f"{key} has {len(value)} items; only the first 3 are displayed")

    if "examples_zh" not in data and "examples_en" not in data:
        report.warn(
            "no examples_zh/examples_en: the detail page will not show 「试试这样用」 cards"
        )

    unknown = [key for key in data if key not in KNOWN_KEYS]
    if unknown:
        report.warn(f"frontmatter keys WorkBuddy ignores: {', '.join(sorted(unknown))}")

    files = _collect(source, keep, extra_excludes)
    if not files:
        report.error("no files selected for packaging")
        return
    plan = _plan(source, files, layout, report)
    paths = plan.final_paths([relative for relative, _ in files])
    report.info["file_count"] = len(paths)
    report.info["files"] = paths
    check_depth(paths, report)
    total = sum(path.stat().st_size for _, path in files)
    report.info["uncompressed_bytes"] = total
    if total > CLOUD_LIMIT_BYTES:
        report.error(f"uncompressed package exceeds the cloud limit ({total} bytes)")


def _stage(
    source_files: list[tuple[str, Path]],
    plan: Plan,
    stage: Path,
) -> list[tuple[str, Path]]:
    """Materialise the planned layout in `stage`, returning (archive-relative, path) entries."""
    entries: list[tuple[str, Path]] = []
    for relative, path in source_files:
        target_relative = plan.renames.get(relative, relative)
        destination = stage / target_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        if relative in plan.patched:
            depth = target_relative.count("/")
            destination.write_text(
                patch_source(path.read_text(encoding="utf-8"), depth), encoding="utf-8"
            )
            destination.chmod(path.stat().st_mode & 0o777)
        entries.append((target_relative, destination))
    return entries


def _compile(entries: list[tuple[str, Path]], report: Report) -> None:
    modules = [str(path) for relative, path in entries if relative.endswith(".py")]
    if not modules:
        return
    completed = subprocess.run(
        [sys.executable, "-m", "py_compile", *modules],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()[-3:]
        report.error("packaged Python sources do not compile: " + " / ".join(detail))


def _write_zip(name: str, entries: list[tuple[str, Path]], output: Path, report: Report) -> None:
    directories = sorted(
        {"/".join(relative.split("/")[:-1]) for relative, _ in entries if "/" in relative}
    )
    handle, temp_name = tempfile.mkstemp(suffix=".zip", dir=str(output.parent))
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for directory in directories:
                info = zipfile.ZipInfo(f"{name}/{directory}/", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFDIR | 0o755) << 16
                archive.writestr(info, b"")
            for relative, path in entries:
                info = zipfile.ZipInfo(f"{name}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | (path.stat().st_mode & 0o777)) << 16
                archive.writestr(info, path.read_bytes())
        shutil.move(str(temp_path), str(output))
        output.chmod(0o644)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def pack(
    source: Path,
    output: Path,
    keep: tuple[str, ...],
    extra_excludes: tuple[str, ...],
    report: Report,
    layout: str = "asis",
) -> None:
    """Write `<name>.zip` containing `<name>/...` for the validated source tree."""
    skill_md = _require_skill_md(source, report)
    if skill_md is None:
        return
    data, _body = load_frontmatter(skill_md.read_text(encoding="utf-8"), Report())
    if data is None:
        report.error("cannot read SKILL.md frontmatter while packing")
        return
    name = str(data.get("name") or source.name)
    files = _collect(source, keep, extra_excludes)
    if not files:
        report.error("no files selected for packaging")
        return
    plan = _plan(source, files, layout, report)
    paths = plan.final_paths([relative for relative, _ in files])
    report.info["skill_name"] = name
    if "depth_offenders" not in report.info:
        check_depth(paths, report)
    if not report.ok:
        report.error("refusing to write an archive that would be rejected on upload")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    if plan.changes:
        with tempfile.TemporaryDirectory(prefix="skillpack-") as directory:
            entries = _stage(files, plan, Path(directory))
            check_depth([relative for relative, _ in entries], report)
            _compile(entries, report)
            if not report.ok:
                report.error("refusing to write an archive from a broken staging tree")
                return
            _write_zip(name, entries, output, report)
    else:
        _write_zip(name, files, output, report)

    size = output.stat().st_size
    report.info["zip_path"] = str(output)
    report.info["zip_bytes"] = size
    if size > CLOUD_LIMIT_BYTES:
        report.error(f"zip is {size} bytes, over the {CLOUD_LIMIT_BYTES} byte limit")
    elif size > WARN_LIMIT_BYTES:
        report.warn(f"zip is {size} bytes, above the {WARN_LIMIT_BYTES} byte warning threshold")


def validate_zip(path: Path, report: Report) -> None:
    """Re-read a finished archive the way the importer would."""
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        roots = {name.split("/", 1)[0] for name in names}
        if len(roots) != 1:
            report.error(f"zip must have exactly one root folder, found {sorted(roots)}")
            return
        root = roots.pop()
        skill_members = [name for name in names if name == f"{root}/SKILL.md"]
        if not skill_members:
            report.error("SKILL.md not found in zip archive")
            return
        inner = [name[len(root) + 1 :] for name in names]
        check_depth(inner, report)
        leaked = [name for name in inner if Path(name).name in INSTALL_META_FILES]
        if leaked:
            report.warn(f"install metadata shipped in package: {', '.join(leaked)}")
        data, _ = load_frontmatter(archive.read(skill_members[0]).decode("utf-8"), Report())
        if data is None:
            report.error("packaged SKILL.md lost its frontmatter")
        else:
            for key in REQUIRED_KEYS:
                if not isinstance(data.get(key), str) or not str(data.get(key)).strip():
                    report.error(f'packaged SKILL.md is missing required field "{key}"')
        report.info["zip_root"] = root
        report.info["zip_files"] = len(names)
        report.info["zip_executable_files"] = [
            info.filename
            for info in archive.infolist()
            if not info.filename.endswith("/") and (info.external_attr >> 16) & 0o111
        ]
