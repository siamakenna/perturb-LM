"""Artifact failures retain useful public phase information without private logs."""

import hashlib
import importlib.util
import io
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
    def failure(
        self, *, failed_command=None, environment_error=False, counts=None, installer_output=""
    ):
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
                if len(calls) == 1:
                    kwargs["stdout"].write(installer_output.encode())
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

    def test_failed_install_includes_only_structured_public_package_facts(self):
        stage, _ = self.failure(
            failed_command=1,
            installer_output=(
                "ERROR: No matching distribution found for numpy==1.26.4\n"
                "ERROR: Error at https://username:secret@example.invalid/private-project\n"
                "private-person /Users/private-person/private-project\n"
            ),
        )
        diagnostic = stage["install_diagnostic"]
        self.assertEqual(diagnostic["categories"], ["no_matching_distribution"])
        self.assertEqual(diagnostic["requirements"], ["numpy==1.26.4"])
        self.assertEqual(diagnostic["conflicts"], [])
        self.assertTrue(diagnostic["unmatched_text_omitted"])

    def test_acceptance_rejection_retains_counts_and_failed_phase(self):
        counts = {"total": 1, "passed": 0, "skipped": 1, "failed": 0, "errors": 0}
        stage, message = self.failure(counts=counts)
        self.assertEqual(stage["failure_step"], "verify_acceptance_counts")
        self.assertEqual(stage["error_type"], "RuntimeError")
        self.assertEqual(stage["counts"], counts)
        self.assertIn("verify_acceptance_counts", message)
        self.assertNotIn("install_diagnostic", stage)


class PublicPipDiagnosticTests(unittest.TestCase):
    def parse(self, text):
        return validator.install_failure_diagnostic(io.BytesIO(text.encode()))

    def test_dependency_conflict_retains_known_requirements_and_public_numeric_versions(self):
        result = self.parse(
            "The conflict is caused by:\n"
            "    The user requested (constraint) numpy==1.26.4\n"
            "    pandas 2.2.3 depends on numpy>=1.22.4\n"
            '    pandas 2.2.3 depends on numpy>=1.26.0; python_version < "3.11"\n'
            "ERROR: ResolutionImpossible: arbitrary text is not copied\n"
        )
        self.assertEqual(result["categories"], ["dependency_resolution_conflict"])
        self.assertEqual(result["requirements"], ["numpy==1.26.4"])
        self.assertEqual(result["conflicts"], [
            {"package": "pandas", "version": "2.2.3", "requires": "numpy>=1.22.4"},
            {"package": "pandas", "version": "2.2.3",
             "requires": 'numpy>=1.26.0; python_version < "3.11"'},
        ])

    def test_paths_urls_unknown_names_extras_and_local_versions_are_never_exported(self):
        secret = "private-secret"
        result = self.parse(
            f"ERROR: No matching distribution found for {secret}\n"
            f"ERROR: No matching distribution found for numpy[{secret}]\n"
            f"ERROR: No matching distribution found for numpy==1.0+{secret}\n"
            f"ERROR: No matching distribution found for numpy @ https://example.invalid/{secret}\n"
            f"ERROR: No matching distribution found for /Users/{secret}/wheel.whl\n"
            f"The user requested (constraint) {secret}==1.0\n"
            f"pandas 2.2.3 depends on {secret}>=1\n"
            f"{secret} 1.0 depends on pandas>=2.2\n"
        )
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["requirements"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["categories"], ["no_matching_distribution"])

    def test_certificate_and_network_diagnostics_do_not_copy_endpoints_or_paths(self):
        result = self.parse(
            "SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] server https://secret.invalid\n"
            "urllib3.exceptions.NewConnectionError: /Users/private-secret/project\n"
        )
        self.assertEqual(result["categories"], [
            "certificate_verification_failed", "network_connection_failed",
        ])
        self.assertNotIn("secret", json.dumps(result))

    def test_unknown_failures_are_explicit_without_fabricated_package_diagnosis(self):
        result = self.parse("an unexpected installer error: private-secret\n")
        self.assertEqual(result["categories"], ["unclassified_install_failure"])
        self.assertEqual(result["requirements"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertNotIn("secret", json.dumps(result))

    def test_only_bounded_tail_is_examined_and_partial_first_line_is_discarded(self):
        text = "ResolutionImpossible\n" + "x" * (64 * 1024)
        result = self.parse(text + "\nERROR: No matching distribution found for numpy==1.26.4\n")
        self.assertTrue(result["log_tail_truncated"])
        self.assertLessEqual(result["tail_bytes_examined"], 64 * 1024)
        self.assertEqual(result["categories"], ["no_matching_distribution"])
        self.assertEqual(result["requirements"], ["numpy==1.26.4"])

    def test_unreadable_log_does_not_mask_original_install_failure(self):
        with tempfile.TemporaryFile("wb") as stream:
            result = validator.install_failure_diagnostic(stream)
        self.assertEqual(result["categories"], ["diagnostic_unavailable"])


if __name__ == "__main__":
    unittest.main()
