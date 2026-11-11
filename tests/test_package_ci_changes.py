import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package_ci_changes.py"
SPEC = importlib.util.spec_from_file_location("package_changes", SCRIPT)
changes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changes)


class PackageCIChangesTests(unittest.TestCase):
    def check_gate(self, event, diff):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, event, clear=True),
            patch("subprocess.run", return_value=diff),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            changes.main()
        self.assertEqual(output.getvalue(), "rebuild=true\n")
        self.assertEqual(errors.getvalue(), "Artifact rebuild required\n")

    def test_synchronize_requires_validation_for_all_changes(self):
        for path in (
            ".github/workflows/package.yml",
            "scripts/package_ci_changes.py",
            "tests/test_package_ci_changes.py",
            "docs/PHASE4_RELEASE_READINESS.md",
            "scripts/build_release_candidate.py",
            "scripts/validate_release_artifacts.py",
            "pyproject.toml",
            "configs/package-minimum.txt",
            "constraints/phase3b-ci.txt",
            "requirements.txt",
            "tests/test_release_contract.py",
            "src/perturb_lm/_version.py",
            "new_unknown_file",
            None,
        ):
            with self.subTest(path=path):
                diff = subprocess.CompletedProcess(
                    ["git", "diff"], 0, stdout=b"" if path is None else path.encode() + b"\0"
                )
                self.check_gate(
                    {"PACKAGE_EVENT_ACTION": "synchronize", "PACKAGE_EVENT_BEFORE": "a" * 40},
                    diff,
                )

    def test_missing_or_uncertain_event_requires_validation(self):
        for event in (
            {},
            {"PACKAGE_EVENT_ACTION": "opened"},
            {"PACKAGE_EVENT_ACTION": "reopened"},
            {"PACKAGE_EVENT_ACTION": "workflow_dispatch"},
            {"PACKAGE_EVENT_ACTION": "synchronize"},
            {"PACKAGE_EVENT_ACTION": "synchronize", "PACKAGE_EVENT_BEFORE": "invalid"},
        ):
            with self.subTest(event=event):
                self.check_gate(event, subprocess.CompletedProcess(["git", "diff"], 0, stdout=b""))

    def test_failed_diff_requires_validation(self):
        self.check_gate(
            {"PACKAGE_EVENT_ACTION": "synchronize", "PACKAGE_EVENT_BEFORE": "a" * 40},
            subprocess.CompletedProcess(["git", "diff"], 1, stdout=b""),
        )

    def test_cli_emits_workflow_output_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=directory,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "rebuild=true\n")
        self.assertEqual(result.stderr, "Artifact rebuild required\n")
