"""Release consistency checks: VERSION, SKILL.md, CHANGELOG, and highlights must agree."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "scripts"):
    sys.path.insert(0, str(path))

from skillpack.frontmatter import parse_frontmatter  # noqa: E402
from skillpack.version import version  # noqa: E402


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    def test_version_format(self) -> None:
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")

    def test_cli_reports_the_repository_version(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "pack.py"), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), f"workbuddy-skill-pack {self.version}")
        self.assertEqual(version(), self.version)

    def test_skill_frontmatter_matches_version(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        data, body = parse_frontmatter(text)
        self.assertIsNotNone(data)
        self.assertEqual(data["name"], ROOT.name)
        self.assertEqual(str(data["version"]), self.version)
        self.assertTrue(body and body.strip())

    def test_changelog_leads_with_the_current_version(self) -> None:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        match = re.search(r"^## ([0-9][^\s]*) - (\d{4}-\d{2}-\d{2})$", text, re.M)
        self.assertIsNotNone(match, "CHANGELOG.md needs a '## <version> - <date>' heading")
        self.assertEqual(match.group(1), self.version)

    def test_highlights_are_present_in_both_languages(self) -> None:
        for name in ("RELEASE_HIGHLIGHTS.md", "RELEASE_HIGHLIGHTS_CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8").strip()
            self.assertTrue(text.startswith("- "), f"{name} must be a bullet list")

    def test_docs_exist(self) -> None:
        for name in ("README.md", "README_CN.md", "LICENSE"):
            self.assertTrue((ROOT / name).is_file(), f"{name} is missing")


if __name__ == "__main__":
    unittest.main()
