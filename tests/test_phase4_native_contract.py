"""Native/toolkit interface checks with synthetic inputs and no model loading.

The proposal inspector, embedding writer, approval validator, and native shell
wrapper are the repository implementations. Shell execution uses a capture-only
interpreter for the worker command. The outer-wrapper test creates a separate
synthetic Git fixture; it never assigns Git identity to an exported source tree.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import comparator_tools  # noqa: E402

from perturb_lm.sklearn_api import pilot  # noqa: E402
from perturb_lm.sklearn_api.datasets import file_checksum  # noqa: E402
from perturb_lm.sklearn_api.workers import save_embedding_stage  # noqa: E402


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        # Keep outputs outside the source tree even when /tmp is unavailable.
        self.temp = tempfile.TemporaryDirectory(prefix="phase4-native-contract-", dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_actual_native_proposal_inspection(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "perturb_lm.sklearn_api.pilot",
                "inspect",
                "--manifest",
                str(ROOT / "configs/pilots/dinov2_v1.json"),
            ],
            cwd=self.root,
            env=dict(
                os.environ,
                PYTHONPATH=str(ROOT / "src"),
                PYTHONDONTWRITEBYTECODE="1",
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
            ),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["execution"], "plan_only")
        self.assertEqual(report["proposed_asset"]["name"], "dinov2")
        self.assertEqual(report["proposed_asset"]["dimension"], 768)
        for key in ("approval_verified", "assets_verified", "inputs_verified"):
            self.assertFalse(report[key])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_native_embedding_writer_to_toolkit_analysis(self):
        vectors = np.eye(3, dtype=np.float32)
        ids = ["synthetic-z", "synthetic-a", "synthetic-b"]
        output = save_embedding_stage(
            vectors,
            ids,
            self.root / "native output",
            {"scope": "synthetic_contract_test", "run_id": "fixture-only"},
        )
        archive = output / "embeddings.npz"
        complete = json.loads((output / "complete.json").read_text())
        self.assertTrue(complete["complete"])
        self.assertEqual(complete["output_checksums"]["embeddings.npz"], file_checksum(archive))
        with np.load(archive, allow_pickle=False) as stored:
            np.testing.assert_array_equal(stored["embeddings"], vectors)
            self.assertEqual(stored["record_ids"].tolist(), ids)
        report = comparator_tools.analyze(
            archive,
            "auto",
            "auto",
            self.root / "analysis",
            2,
            3,
            True,
            True,
        )
        self.assertEqual(report["n_records"], 3)
        self.assertEqual(report["npz_vector_key"], "embeddings")
        self.assertEqual(report["npz_id_key"], "record_ids")
        self.assertEqual(report["stored_dtype"], "float32")
        self.assertTrue(report["unit_norms_within_1e_5"])
        self.assertEqual(report["scope"], "descriptive_feature_geometry_not_retrieval_accuracy")
        self.assertFalse(report["native_completion_verified"])

    def test_native_plan_only_rejects_before_model_loading(self):
        with mock.patch.object(pilot, "LocalModelEmbedder") as encoder:
            with self.assertRaisesRegex(PermissionError, "plan_only"):
                pilot.run_pilot(
                    ROOT / "configs/pilots/dinov2_v1.json",
                    data_root=self.root,
                    asset_root=self.root,
                    output=self.root / "output",
                )
            encoder.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_native_mismatched_approval_binding_rejects(self):
        write_json(self.root / "asset.json", {"fixture": "not a model asset"})
        approval = write_json(
            self.root / "approval.json",
            {
                "schema_version": 1,
                "source_commit": "wrong-source",
                "pilot_sha256": "wrong-pilot",
                "asset_manifest_sha256": "wrong-asset",
            },
        )
        with mock.patch.object(pilot, "LocalModelEmbedder") as encoder:
            with self.assertRaisesRegex(PermissionError, "does not bind"):
                pilot.approval_for(
                    {"model": "dinov2"},
                    approval,
                    {"git_commit": "explicit-test-fixture"},
                    self.root,
                )
            encoder.assert_not_called()

    def test_native_missing_approval_stops_before_inputs_or_model(self):
        payload = json.loads((ROOT / "configs/pilots/dinov2_v1.json").read_text())
        payload["execution"] = "approved_inference"
        payload["dataset"]["metadata_sha256"] = "0" * 64
        manifest = write_json(self.root / "manifest.json", payload)
        # Isolate Git only: source exports do not carry original Git identity.
        with (
            mock.patch.object(
                pilot, "code_identity", return_value={"git_commit": "explicit-test-fixture"}
            ),
            mock.patch.object(pilot.subprocess, "check_output", return_value=""),
            mock.patch.object(pilot, "checked_path") as input_reader,
            mock.patch.object(pilot, "LocalModelEmbedder") as encoder,
        ):
            with self.assertRaisesRegex(PermissionError, "Explicit recorded approvals"):
                pilot.run_pilot(
                    manifest, data_root=self.root, asset_root=self.root, output=self.root / "output"
                )
            input_reader.assert_not_called()
            encoder.assert_not_called()
        self.assertFalse((self.root / "output").exists())


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "requires Git and Bash")
class NativeWrapperContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="phase4-wrapper-contract-", dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = self.root / "synthetic code with spaces"
        self.code.mkdir()
        native_wrapper = self.code / "slurm/phase4_pilot.sbatch"
        native_wrapper.parent.mkdir()
        # Preserve the actual native shell program, with no worker implementation.
        native_wrapper.write_bytes((ROOT / "slurm/phase4_pilot.sbatch").read_bytes())
        self.data = self.root / "synthetic data with spaces"
        self.data.mkdir()
        self.approval = write_json(self.data / "synthetic approval.json", {})
        self.assets = self.root / "synthetic assets with spaces"
        self.assets.mkdir()
        write_json(self.assets / "asset.json", {"fixture": "not a model asset"})
        self.manifest = write_json(
            self.root / "synthetic manifest.json",
            {
                "model": "dinov2",
                "execution": "approved_inference",
                "max_inputs": 1,
            },
        )
        self.output = self.root / "absent pilot output"
        self.capture = self.root / "captured invocation.json"
        envroot = self.root / "capture environment with spaces"
        executable = envroot / "bin/python"
        executable.parent.mkdir(parents=True)
        capture_script = envroot / "capture.py"
        capture_script.write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "if sys.argv[1:2] == ['-']:\n"
            "    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
            "if sys.argv[1:4] != ['-m', 'perturb_lm.sklearn_api.pilot', 'run']:\n"
            "    raise SystemExit('Unexpected command to capture-only interpreter')\n"
            "Path(os.environ['CAPTURE_ARGV']).write_text(json.dumps({\n"
            "    'argv': sys.argv[1:], 'cwd': str(Path.cwd()),\n"
            "    'offline': [os.environ.get('HF_HUB_OFFLINE'),\n"
            "                os.environ.get('TRANSFORMERS_OFFLINE')]}))\n"
        )
        # Kernel shebang parsing cannot quote an interpreter path containing spaces.
        # Keep the selected environment by launching it through a quoted shell exec.
        executable.write_text(
            "#!/bin/sh\n"
            f'exec {shlex.quote(sys.executable)} {shlex.quote(str(capture_script))} "$@"\n'
        )
        executable.chmod(0o700)
        module_dir = self.root / "module stub"
        module_dir.mkdir()
        module = module_dir / "module"
        module.write_text('#!/bin/sh\n[ "$1" = load ] && [ "$2" = python/3.11 ]\n')
        module.chmod(0o700)
        tool_dirs = {str(Path(shutil.which(name)).parent) for name in ("git", "bash")}
        self.env = {
            "PATH": os.pathsep.join([str(module_dir), *sorted(tool_dirs), os.defpath]),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "CAPTURE_ARGV": str(self.capture),
            "SLURM_JOB_ID": "synthetic-contract-only",
        }
        self.variables = {
            "PILOT_CODE": str(self.code),
            "PILOT_ENV": str(envroot),
            "PILOT_MANIFEST": str(self.manifest),
            "PILOT_APPROVAL": str(self.approval.relative_to(self.data)),
            "PILOT_DATA": str(self.data),
            "PILOT_ASSETS": str(self.assets),
            "PILOT_OUT": str(self.output),
        }

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.code), *args],
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )

    def assert_captured_native_contract(self):
        captured = json.loads(self.capture.read_text())
        expected = [
            "-m",
            "perturb_lm.sklearn_api.pilot",
            "run",
            "--manifest",
            str(self.manifest),
            "--approval",
            self.approval.name,
            "--data-root",
            str(self.data),
            "--asset-root",
            str(self.assets),
            "--out",
            str(self.output),
        ]
        self.assertEqual(captured["argv"], expected)
        self.assertEqual(captured["cwd"], str(self.code))
        self.assertEqual(captured["offline"], ["1", "1"])
        self.assertFalse(self.output.exists())

    def test_actual_native_wrapper_argument_handoff(self):
        result = subprocess.run(
            ["bash", str(self.code / "slurm/phase4_pilot.sbatch")],
            cwd=self.data,
            env={**self.env, **self.variables},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_captured_native_contract()

    def test_outer_wrapper_delegates_to_actual_native_wrapper(self):
        # This new Git history identifies only this disposable synthetic fixture.
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
            "Synthetic native-wrapper fixture",
        )
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        files = [
            self.manifest,
            self.approval,
            self.assets / "asset.json",
            self.code / "slurm/phase4_pilot.sbatch",
        ]
        bindings = write_json(
            self.root / "bindings.json", {str(path): file_checksum(path) for path in files}
        )
        variables = dict(
            self.variables,
            PILOT_EXPECTED_SHA=sha,
            PILOT_BINDINGS=str(bindings),
            PILOT_BINDINGS_SHA256=file_checksum(bindings),
        )
        session = self.root / "launch with spaces.env.sh"
        session.write_text(
            "".join(f"export {key}={shlex.quote(value)}\n" for key, value in variables.items())
        )
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "slurm/run_dinov2_once.sbatch"),
                str(session),
                "I_AUTHORIZE_ONE_DINOV2_PILOT",
            ],
            # Starting outside data makes the native relative-file check meaningful.
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Prelaunch file bindings match", result.stdout)
        self.assert_captured_native_contract()
        self.assertEqual(self.git("status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
