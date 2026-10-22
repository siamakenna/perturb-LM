"""Artifact failures retain useful public phase information without private logs."""

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "release_artifact_validator",
    Path(__file__).resolve().parents[1] / "scripts/validate_release_artifacts.py",
)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArtifactFailureDiagnosticsTests(unittest.TestCase):
    def failure(self, *, failed_command=None, environment_error=False, counts=None):
        outside_repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=outside_repository) as temporary:
            root = Path(temporary)
            dist, out = root / "dist", root / "out"
            dist.mkdir()
            artifacts = {}
            for name in ("perturb_lm-0.2.0a1-py3-none-any.whl", "perturb_lm-0.2.0a1.tar.gz"):
                data = name.encode()
                (dist / name).write_bytes(data)
                artifacts[name] = hashlib.sha256(data).hexdigest()
            manifest = {
                "status": "BUILT_NOT_RELEASED", "source_unchanged": True,
                "source_commit": "a" * 40, "version": "0.2.0a1", "artifacts": artifacts,
            }
            (dist / "provenance.json").write_text(json.dumps(manifest))
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if len(calls) == failed_command:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0)

            def create(path):
                if environment_error:
                    raise OSError("private message /Users/private-person/private-project")

            argv = ["validate_release_artifacts.py", "--dist", str(dist), "--out", str(out)]
            versions = json.dumps({"python": "3.10.0", "packages": {}})
            with (
                patch.object(sys, "argv", argv),
                patch.object(validator.tempfile, "tempdir", temporary),
                patch.object(
                    validator.venv, "EnvBuilder", return_value=SimpleNamespace(create=create)
                ),
                patch.object(validator.subprocess, "run", side_effect=run),
                patch.object(validator.subprocess, "check_output", return_value=versions),
                patch.object(validator, "counts", return_value=counts),
                self.assertRaises(SystemExit) as stopped,
            ):
                validator.main()
            text = (out / "summary.json").read_text()
            summary = json.loads(text)
            self.assertEqual(summary["overall"], "REVIEW_REQUIRED")
            self.assertEqual(summary["validator_python"], platform.python_version())
            self.assertEqual(summary["artifact_sha256"], artifacts)
            self.assertNotIn(str(root), text)
            self.assertNotIn("private-person", text)
            self.assertNotIn("private-project", text)
            self.assertNotIn("command", summary["stages"]["wheel-base"])
            return summary["stages"]["wheel-base"], str(stopped.exception)

    def test_subprocess_failure_reports_exact_phase_without_command_arguments(self):
        for index, phase in enumerate(
            (
                "install_dependencies",
                "check_dependencies",
                "verify_installed_origin_and_isolation",
                "run_acceptance_tests",
            ),
            start=1,
        ):
            with self.subTest(phase=phase):
                stage, message = self.failure(failed_command=index)
                self.assertEqual(stage["failure_step"], phase)
                self.assertEqual(stage["error_type"], "CalledProcessError")
                self.assertEqual(stage["exit_code"], 1)
                self.assertEqual(stage["status"], "REVIEW_REQUIRED")
                self.assertIn(phase, message)

    def test_environment_failure_is_distinct_from_install_failure(self):
        stage, message = self.failure(environment_error=True)
        self.assertEqual(stage["failure_step"], "create_environment")
        self.assertEqual(stage["error_type"], "OSError")
        self.assertIsNone(stage["exit_code"])
        self.assertIn("create_environment", message)

    def test_acceptance_rejection_retains_counts_and_failed_phase(self):
        counts = {"total": 1, "passed": 0, "skipped": 1, "failed": 0, "errors": 0}
        stage, message = self.failure(counts=counts)
        self.assertEqual(stage["failure_step"], "verify_acceptance_counts")
        self.assertEqual(stage["error_type"], "RuntimeError")
        self.assertEqual(stage["counts"], counts)
        self.assertIn("verify_acceptance_counts", message)


if __name__ == "__main__":
    unittest.main()
