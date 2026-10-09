"""Synthetic launcher regressions using only the Python standard library.

The Git checkout is real but contains test-only source stubs. Preparation's
Python import and native inspection calls are mocked; Git and the outer shell
wrapper run locally. The delegated shell stub only records environment values.
No native Perturb-LM implementation, Slurm job, model or download is exercised.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_native_launch as launcher


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "requires Git and Bash")
class LaunchRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-launch-")
        self.addCleanup(self.temp.cleanup)
        # Canonicalize directory aliases before constructing fixture paths.
        self.root = Path(self.temp.name).resolve()
        self.code = self.root / "code with spaces"
        self.code.mkdir()
        worker = self.code / "src/perturb_lm/sklearn_api/pilot.py"
        worker.parent.mkdir(parents=True)
        worker.write_text("# Test-only placeholder; never imported or executed.\n")
        native_wrapper = self.code / "slurm/phase4_pilot.sbatch"
        native_wrapper.parent.mkdir()
        native_wrapper.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            "# Harmless test-only delegation target; does not run a worker.\n"
            'test "$PWD" = "$PILOT_DATA"\n'
            'test -f "$PILOT_APPROVAL"\n'
            'printf \'%s\\n\' "$PILOT_CODE" "$PILOT_ENV" "$PILOT_MANIFEST" '
            '"$PILOT_APPROVAL" "$PILOT_DATA" "$PILOT_ASSETS" "$PILOT_OUT" '
            '"$PILOT_EXPECTED_SHA" > "$STUB_CAPTURE"\n'
        )
        self.module_dir = self.root / "stub-bin"
        self.module_dir.mkdir()
        module = self.module_dir / "module"
        module.write_text('#!/bin/sh\n[ "$1" = load ] && [ "$2" = python/3.11 ]\n')
        module.chmod(0o700)
        tool_dirs = {str(Path(shutil.which(name)).parent) for name in ("git", "bash")}
        self.env = {
            "PATH": os.pathsep.join([str(self.module_dir), *sorted(tool_dirs), os.defpath]),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.git("init", "--quiet", "--template=")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Synthetic Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            "commit",
            "--quiet",
            "-m",
            "Synthetic launcher fixture",
        )
        self.sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.data = self.root / "data with spaces"
        self.data.mkdir()
        self.assets = self.root / "assets"
        self.assets.mkdir()
        write_json(self.assets / "asset.json", {"fixture": "not a native asset inventory"})
        self.image = self.data / "one.tif"
        self.image.write_bytes(b"opaque fixture bytes; no TIFF decoding is performed")
        inventory = write_json(
            self.data / "inventory.json",
            [{"record_id": "one", "path": "one.tif", "sha256": launcher.digest(self.image)}],
        )
        self.manifest = write_json(
            self.root / "manifest.json",
            {
                "model": "dinov2",
                "execution": "approved_inference",
                "max_inputs": 1,
                "resources": {"cpus": 2, "gpus": 0, "memory_gb": 8, "time": "00:10:00"},
                "dataset": {
                    "synthetic": False,
                    "version": "fixture-not-a-real-dataset",
                    "metadata_path": "inventory.json",
                    "metadata_sha256": launcher.digest(inventory),
                },
            },
        )
        approval_dir = self.data / "review records"
        approval_dir.mkdir()
        self.approval = write_json(approval_dir / "approval.json", {"source_commit": self.sha})
        self.pilot_out = self.root / "pilot output"
        self.request = write_json(
            self.root / "request.json",
            {
                "manifest": str(self.manifest),
                "approval": str(self.approval),
                "data_root": str(self.data),
                "asset_root": str(self.assets),
                "pilot_output": str(self.pilot_out),
            },
        )
        self.python = self.root / "env with spaces/bin/python"
        self.python.parent.mkdir(parents=True)
        self.python.symlink_to(sys.executable)
        self.out = self.root / "launch preparation"
        self.capture = self.root / "stub-delegation.txt"
        self.python_calls = []

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.code), *args],
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )

    def prepare(self, during_inspection=None):
        real_run = subprocess.run

        def run(args, **kwargs):
            if args[0] == str(self.python):
                self.python_calls.append(args)
                self.assertNotIn("run", args)
                if "inspect" in args and during_inspection:
                    during_inspection()
                return subprocess.CompletedProcess(args, 0)
            return real_run(args, **kwargs)

        with mock.patch.dict(os.environ, self.env, clear=True):
            with mock.patch.object(launcher.subprocess, "run", side_effect=run):
                return launcher.prepare(self.request, self.code, self.python, self.sha, self.out)

    def shell_handoff(self, authorization="I_AUTHORIZE_ONE_DINOV2_PILOT"):
        env = dict(self.env, SLURM_JOB_ID="synthetic-test-only", STUB_CAPTURE=str(self.capture))
        wrapper = Path(launcher.__file__).resolve().parents[1] / "slurm/run_dinov2_once.sbatch"
        return subprocess.run(
            ["bash", str(wrapper), str(self.out / "launch.env.sh"), authorization],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_mocked_preparation_to_real_shell_delegation(self):
        report = self.prepare()
        self.assertFalse(report["pretrained_inference_performed"])
        self.assertFalse(report["submission_authorized_by_this_program"])
        self.assertEqual(len(self.python_calls), 2)
        self.assertIn("inspect", self.python_calls[1])
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o700)
        result = self.shell_handoff()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = [
            self.code,
            self.python.parent.parent,
            self.manifest,
            self.approval.relative_to(self.data),
            self.data,
            self.assets,
            self.pilot_out,
            self.sha,
        ]
        self.assertEqual(self.capture.read_text().splitlines(), [str(v) for v in expected])
        self.assertFalse(self.pilot_out.exists())
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_preparation_cannot_create_the_pilot_output(self):
        request = json.loads(self.request.read_text())
        request["pilot_output"] = str(self.out)
        write_json(self.request, request)
        with self.assertRaisesRegex(ValueError, "must differ"):
            self.prepare()
        self.assertFalse(self.out.exists())
        self.assertEqual(self.python_calls, [])

    def test_malformed_dataset_is_a_validation_error(self):
        manifest = json.loads(self.manifest.read_text())
        for value in (None, [], "not-an-object", 5):
            with self.subTest(dataset=value):
                manifest["dataset"] = value
                write_json(self.manifest, manifest)
                with self.assertRaisesRegex(ValueError, "dataset must be a JSON object"):
                    launcher.validate_request(self.request, self.code, self.sha)

    def test_approval_outside_data_root_is_rejected(self):
        outside = write_json(self.root / "outside-approval.json", {"source_commit": self.sha})
        request = json.loads(self.request.read_text())
        request["approval"] = str(outside)
        write_json(self.request, request)
        with self.assertRaisesRegex(ValueError, "Approval must resolve inside"):
            self.prepare()
        self.assertFalse(self.out.exists())
        self.assertEqual(self.python_calls, [])

    def test_approval_symlink_escape_is_rejected(self):
        outside = write_json(self.root / "outside-approval.json", {"source_commit": self.sha})
        self.approval.unlink()
        self.approval.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "Approval must resolve inside"):
            self.prepare()
        self.assertFalse(self.out.exists())

    def test_preparation_rejects_existing_working_output(self):
        self.pilot_out.with_name(self.pilot_out.name + ".working").mkdir()
        with self.assertRaisesRegex(ValueError, "fresh output"):
            self.prepare()
        self.assertFalse(self.out.exists())
        self.assertEqual(self.python_calls, [])

    def test_shell_rejects_working_output_before_delegation(self):
        self.prepare()
        self.pilot_out.with_name(self.pilot_out.name + ".working").mkdir()
        result = self.shell_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.capture.exists())

    def test_launch_rejects_native_missing_record_ids(self):
        inventory_path = self.data / "inventory.json"
        rows = json.loads(inventory_path.read_text())
        rows[0]["record_id"] = "NuLl"
        write_json(inventory_path, rows)
        manifest = json.loads(self.manifest.read_text())
        manifest["dataset"]["metadata_sha256"] = launcher.digest(inventory_path)
        write_json(self.manifest, manifest)
        with self.assertRaisesRegex(ValueError, "missing-value placeholders"):
            self.prepare()
        self.assertFalse(self.out.exists())

    def test_change_during_mocked_inspection_does_not_publish_launch(self):
        with self.assertRaisesRegex(ValueError, "changed during inspection"):
            self.prepare(lambda: self.image.write_bytes(b"changed during inspection"))
        self.assertFalse((self.out / "launch.env.sh").exists())
        self.assertFalse((self.out / "preparation-summary.json").exists())

    def test_shell_rejects_changed_bound_input_before_delegation(self):
        self.prepare()
        self.image.write_bytes(b"changed after preparation")
        result = self.shell_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file changed after launch preparation", result.stdout + result.stderr)
        self.assertFalse(self.capture.exists())

    def test_shell_requires_authorization_before_delegation(self):
        self.prepare()
        result = self.shell_handoff(authorization="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit operator authorization", result.stdout)
        self.assertFalse(self.capture.exists())


if __name__ == "__main__":
    unittest.main()
