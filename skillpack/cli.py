"""Command-line interface for the WorkBuddy skill packager."""

from __future__ import annotations

import argparse
from pathlib import Path

from .frontmatter import parse_frontmatter
from .layout import LAYOUTS
from .packer import pack, validate_source, validate_zip
from .report import Report
from .version import version


def skill_name(source: Path) -> str:
    """Frontmatter name when readable, otherwise the directory name."""
    skill_md = source / "SKILL.md"
    if skill_md.is_file():
        try:
            data, _body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except OSError:
            data = None
        if data and isinstance(data.get("name"), str) and data["name"].strip():
            return str(data["name"]).strip()
    return source.name


def resolve_targets(args: argparse.Namespace) -> tuple[Path, Path | None]:
    source = Path(args.skill_dir).expanduser().resolve()
    if source.is_file():
        if source.name != "SKILL.md":
            raise SystemExit(f"{source} is not a directory and not a SKILL.md file")
        source = source.parent
    if not source.is_dir():
        raise SystemExit(f"{source} is not a directory")
    if args.check:
        return source, None
    if args.output is None:
        raise SystemExit("--output is required unless --check is used")
    output = Path(args.output).expanduser()
    if output.suffix.lower() != ".zip":
        output = output / f"{skill_name(source)}.zip"
    return source, output.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pack.py",
        description="Build and validate a WorkBuddy/SkillHub skill package.",
    )
    parser.add_argument(
        "skill_dir",
        nargs="?",
        help="skill source directory, its SKILL.md, or an existing .zip",
    )
    parser.add_argument("-o", "--output", help="output .zip path, or a directory to place <name>.zip in")
    parser.add_argument("--check", action="store_true", help="validate only, write no zip")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="GLOB",
        help="re-include files matching GLOB (e.g. --keep '*.slurm')",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude extra paths, matched against the path relative to the skill root",
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUTS,
        default="asis",
        help="asis (default) or workbuddy, which lifts nested Python packages to the skill root "
        "for the packaged copy only",
    )
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    parser.add_argument("--version", action="store_true", help="print the packager version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"workbuddy-skill-pack {version()}")
        return 0
    if not args.skill_dir:
        parser.error("skill_dir is required")

    target = Path(args.skill_dir).expanduser()
    if target.suffix.lower() == ".zip" and target.is_file():
        report = Report()
        validate_zip(target, report)
        resolved = target.resolve()
        report.info["zip_path"] = str(resolved)
        report.info["zip_bytes"] = resolved.stat().st_size
        return report.emit(str(resolved), args.json)

    source, output = resolve_targets(args)
    keep = tuple(args.keep)
    excludes = tuple(args.exclude)
    report = Report()
    validate_source(source, keep, excludes, report, layout=args.layout)
    if report.ok and output is not None:
        pack(source, output, keep, excludes, report, layout=args.layout)
        if report.ok:
            validate_zip(output, report)
    return report.emit(str(source), args.json)
