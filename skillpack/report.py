"""Validation report shared by the packager, the CLI, and the tests."""

from __future__ import annotations

import json


class Report:
    """Collects fatal errors, warnings, and informational facts about a package."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: dict[str, object] = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self, label: str) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": label,
            "zip_path": self.info.get("zip_path"),
            "zip_bytes": self.info.get("zip_bytes"),
            "file_count": self.info.get("file_count", self.info.get("zip_files")),
            "errors": self.errors,
            "warnings": self.warnings,
            "details": {key: value for key, value in self.info.items() if key != "files"},
        }

    def emit(self, label: str, as_json: bool = False) -> int:
        """Print the report and return a process exit code."""
        if as_json:
            print(json.dumps(self.summary(label), ensure_ascii=False, indent=2))
            return 0 if self.ok else 1
        summary = self.summary(label)
        print(f"target: {label}")
        if summary["zip_path"]:
            print(f"zip:    {summary['zip_path']} ({summary['zip_bytes']} bytes)")
        print(f"files:  {summary['file_count']}")
        for warning in self.warnings:
            print(f"  warn: {warning}")
        for error in self.errors:
            print(f"  FAIL: {error}")
        print("result:", "OK" if self.ok else "INVALID")
        return 0 if self.ok else 1
