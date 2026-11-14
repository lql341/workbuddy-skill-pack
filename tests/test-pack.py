"""Regression tests for the WorkBuddy skill packager."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "scripts"):
    sys.path.insert(0, str(path))

from skillpack import cli  # noqa: E402
from skillpack.frontmatter import load_frontmatter, parse_minimal  # noqa: E402
from skillpack.packer import pack, validate_source, validate_zip  # noqa: E402
from skillpack.report import Report  # noqa: E402
from skillpack.rules import CLOUD_LIMIT_BYTES, iter_files  # noqa: E402

SKILL = """---
name: demo-skill
description: Demo skill used by the packager tests.
version: 0.1.0
examples_zh:
  - 第一条引导问题
  - 第二条引导问题
---

# Demo

Body text that is long enough to look like real instructions for the packager.
"""


def make_skill(root: Path, body: str = SKILL, files: dict[str, str] | None = None) -> Path:
    skill = root / "demo-skill"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")
    for relative, content in (files or {"scripts/run.sh": "#!/bin/sh\necho hi\n"}).items():
        target = skill / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if relative.endswith(".sh"):
            target.chmod(0o755)
    return skill


class FrontmatterTests(unittest.TestCase):
    def test_minimal_parser_reads_scalars_and_lists(self) -> None:
        data = parse_minimal(
            "name: demo\ndescription: 'quoted value'\nexamples_zh:\n  - one\n  - \"two\"\n"
        )
        self.assertEqual(data["name"], "demo")
        self.assertEqual(data["description"], "quoted value")
        self.assertEqual(data["examples_zh"], ["one", "two"])

    def test_missing_frontmatter_is_reported(self) -> None:
        report = Report()
        data, _body = load_frontmatter("# No frontmatter\n", report)
        self.assertIsNone(data)
        self.assertEqual(report.warnings, [])  # the missing-frontmatter error belongs to validation

    def test_invalid_yaml_is_reported(self) -> None:
        report = Report()
        data, _body = load_frontmatter("---\nname: [unclosed\n---\n", report)
        self.assertIsNone(data)
        self.assertTrue(any("not valid YAML" in error for error in report.errors))


class RuleTests(unittest.TestCase):
    def test_dev_artifacts_and_install_metadata_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(
                Path(directory),
                files={
                    "scripts/run.sh": "#!/bin/sh\n",
                    "_skillhub_meta.json": "{}",
                    ".DS_Store": "x",
                    "notes.pyc": "x",
                    "probe.slurm": "x",
                },
            )
            (skill / "tests").mkdir()
            (skill / "tests" / "test_x.py").write_text("", encoding="utf-8")
            (skill / ".github").mkdir()
            (skill / ".github" / "workflows.yml").write_text("", encoding="utf-8")
            selected = [relative for relative, _ in iter_files(skill, (), ())]
            self.assertEqual(selected, ["SKILL.md", "scripts/run.sh"])

    def test_keep_restores_excluded_globs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory), files={"probe.slurm": "x"})
            self.assertEqual([r for r, _ in iter_files(skill, (), ())], ["SKILL.md"])
            self.assertEqual(
                [r for r, _ in iter_files(skill, ("*.slurm",), ())],
                ["SKILL.md", "probe.slurm"],
            )

    def test_nested_package_violates_depth_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory), files={"scripts/pkg/mod.py": "x = 1\n"})
            report = Report()
            validate_source(skill, (), (), report)
            self.assertFalse(report.ok)
            self.assertIn("目录层级超限", report.errors[0])
            self.assertIn("scripts/pkg/mod.py", report.errors[0])

    def test_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory), body="---\nname: demo\n---\n\n# Demo\n")
            report = Report()
            validate_source(skill, (), (), report)
            self.assertTrue(
                any('Required field "description"' in error for error in report.errors)
            )

    def test_oversized_package_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory))
            with (skill / "big.bin").open("wb") as handle:
                handle.seek(CLOUD_LIMIT_BYTES + 1)
                handle.write(b"\0")
            report = Report()
            validate_source(skill, (), (), report)
            self.assertTrue(any("cloud limit" in error for error in report.errors))

    def test_examples_are_surfaced_for_the_detail_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory))
            report = Report()
            validate_source(skill, (), (), report)
            self.assertFalse(any("试试这样用" in warning for warning in report.warnings))

    def test_missing_examples_warns_about_detail_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(
                Path(directory), body="---\nname: demo\n---\n\ndescription: demo\n"
            )
            report = Report()
            validate_source(skill, (), (), report)
            self.assertTrue(any("试试这样用" in warning for warning in report.warnings))


class PackagingTests(unittest.TestCase):
    def test_package_layout_permissions_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = make_skill(root)
            output = root / "demo-skill.zip"
            report = Report()
            pack(skill, output, (), (), report)
            self.assertTrue(report.ok, report.errors)
            validate_zip(output, report)
            self.assertTrue(report.ok, report.errors)

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("demo-skill/SKILL.md", names)
                self.assertIn("demo-skill/scripts/run.sh", names)
                mode = archive.getinfo("demo-skill/scripts/run.sh").external_attr >> 16
                self.assertTrue(mode & 0o111, "exec bit must survive packaging")
            self.assertEqual(report.info["zip_root"], "demo-skill")

    def test_pack_refuses_a_too_deep_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = make_skill(root, files={"scripts/pkg/mod.py": "x = 1\n"})
            output = root / "demo-skill.zip"
            report = Report()
            pack(skill, output, (), (), report)
            self.assertFalse(report.ok)
            self.assertFalse(output.exists(), "no archive may be written for an invalid tree")
            self.assertTrue(any("目录层级超限" in error for error in report.errors))

    def test_zip_without_skill_md_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "broken.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("demo-skill/README.md", "no skill file")
            report = Report()
            validate_zip(archive_path, report)
            self.assertIn("SKILL.md not found in zip archive", report.errors)

    def test_zip_with_two_roots_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "broken.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("one/SKILL.md", SKILL)
                archive.writestr("two/SKILL.md", SKILL)
            report = Report()
            validate_zip(archive_path, report)
            self.assertTrue(any("exactly one root folder" in error for error in report.errors))


class CliTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_check_reports_ok_and_prints_nothing_else(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory))
            code, output = self.run_cli([str(skill), "--check"])
            self.assertEqual(code, 0)
            self.assertIn("result: OK", output)

    def test_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = make_skill(Path(directory))
            code, output = self.run_cli([str(skill), "--check", "--json"])
            self.assertEqual(code, 0)
            self.assertIn('"ok": true', output)

    def test_build_writes_zip_into_directory_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = make_skill(root)
            out_dir = root / "out"
            code, _output = self.run_cli([str(skill), "-o", str(out_dir)])
            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "demo-skill.zip").is_file())

    def test_default_zip_name_uses_frontmatter_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "folder-name"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                SKILL.replace("demo-skill", "canonical-name"), encoding="utf-8"
            )
            out_dir = root / "out"
            code, output = self.run_cli([str(skill), "-o", str(out_dir)])
            self.assertEqual(code, 0, output)
            self.assertTrue((out_dir / "canonical-name.zip").is_file())
            self.assertIn("differs from frontmatter name", output)

    def test_existing_zip_can_be_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = make_skill(root)
            code, _ = self.run_cli([str(skill), "-o", str(root)])
            self.assertEqual(code, 0)
            code, output = self.run_cli([str(root / "demo-skill.zip")])
            self.assertEqual(code, 0, output)

    def test_version_flag(self) -> None:
        code, output = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertRegex(output.strip(), r"^workbuddy-skill-pack \d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
