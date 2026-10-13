import json
import os
import subprocess
import sys

import pytest

from perturb_lm.sklearn_api import pilot
from perturb_lm.sklearn_api.datasets import file_checksum
from perturb_lm.sklearn_api.planning import canonical_hash


@pytest.mark.parametrize("family", ["dinov2", "sapbert"])
def test_proposal_inspect_and_execution_rejected(family, tmp_path):
    path = pilot.ROOT / f"configs/pilots/{family}_v1.json"
    result = subprocess.run(
        [sys.executable, "-m", "perturb_lm.sklearn_api.pilot", "inspect", "--manifest", str(path)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PYTHONPATH=str(pilot.ROOT / "src")),
    )
    summary = json.loads(result.stdout)
    assert summary["execution"] == "plan_only"
    assert summary["approval_verified"] is False
    with pytest.raises(PermissionError, match="plan_only"):
        pilot.run_pilot(path, data_root=tmp_path, asset_root=tmp_path, output=tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"max_inputs": 9},
        {"batch_size": 3},
        {"model": "cellclip"},
        {"execution": "production"},
        {"unexpected": True},
    ],
)
def test_pilot_bounds_and_unknown_contracts_fail(change, tmp_path):
    payload = json.loads((pilot.ROOT / "configs/pilots/dinov2_v1.json").read_text())
    payload.update(change)
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        pilot.load_pilot(path)


def test_approval_binds_exact_source_manifest_asset_and_owner(tmp_path):
    payload = {"model": "dinov2"}
    code = {"git_commit": "a" * 40}
    (tmp_path / "asset.json").write_text("{}")
    with pytest.raises(PermissionError):
        pilot.approval_for(payload, None, code, tmp_path)
    record = {
        "schema_version": 1,
        "source_commit": code["git_commit"],
        "pilot_sha256": canonical_hash(payload),
        "asset_manifest_sha256": file_checksum(tmp_path / "asset.json"),
        "decisions": {
            kind: {
                "status": "approved",
                "reviewer": "siamakenna",
                "reference": "https://github.com/siamakenna/perturb-LM/issues/55#issuecomment-123",
            }
            for kind in ("asset_use", "input_use", "scientific_protocol")
        },
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(record))
    assert pilot.approval_for(payload, path, code, tmp_path) == canonical_hash(record)
    for key in ("source_commit", "pilot_sha256", "asset_manifest_sha256"):
        bad = dict(record, **{key: "b" * 64})
        path.write_text(json.dumps(bad))
        with pytest.raises(PermissionError):
            pilot.approval_for(payload, path, code, tmp_path)
    record["decisions"]["scientific_protocol"]["reviewer"] = "adamdiaz313-collab"
    path.write_text(json.dumps(record))
    with pytest.raises(PermissionError, match="owner"):
        pilot.approval_for(payload, path, code, tmp_path)


def test_input_paths_and_hashes_fail_closed(tmp_path):
    (tmp_path / "input").write_text("local")
    tracked = {}
    for relative, checksum in (("../input", ""), ("input", "0" * 64)):
        with pytest.raises(ValueError):
            pilot.checked_path(tmp_path, relative, checksum, tracked)
    assert not tracked


def test_unapproved_real_request_stops_before_loading_inputs(tmp_path, monkeypatch):
    payload = json.loads((pilot.ROOT / "configs/pilots/sapbert_v1.json").read_text())
    payload["execution"] = "approved_inference"
    payload["dataset"]["metadata_sha256"] = "0" * 64
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(pilot, "code_identity", lambda root: {"git_commit": "a" * 40})
    monkeypatch.setattr(pilot.subprocess, "check_output", lambda *args, **kwargs: "")
    with pytest.raises(PermissionError, match="Explicit recorded approvals"):
        pilot.run_pilot(path, data_root=tmp_path, asset_root=tmp_path, output=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_slurm_requires_explicit_local_values():
    result = subprocess.run(
        ["bash", str(pilot.ROOT / "slurm/phase4_pilot.sbatch")],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "reviewed compute allocation" in result.stderr
