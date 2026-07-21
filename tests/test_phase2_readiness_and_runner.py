from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from scripts.check_phase2_readiness import check_phase2_readiness
from scripts.run_phase2_jump_smoke import write_synthetic_jump_pilot
from scripts.run_phase2_local_report import run_phase2_local_report


def test_run_phase2_local_report_writes_manifest_and_report(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_synthetic_jump_pilot(data_root)
    out = tmp_path / "phase2_report"

    manifest = run_phase2_local_report(
        data_root=data_root,
        out_dir=out,
        top_k=[1, 2],
        seed=7,
    )

    assert manifest["dataset_track"] == "JUMP CPJUMP1 profiles"
    assert manifest["indexed_profile_rows"] == 6
    assert "identifier_stripped_tfidf" in manifest["text_profile_modes"]
    assert (out / "phase2_jump_report.md").exists()
    assert (out / "baseline_manifest.json").exists()
    assert (out / "diagnostics" / "leakage_summary.csv").exists()
    assert (out / "diagnostics" / "leakage_summary.json").exists()
    assert (out / "diagnostics" / "dashboard_leakage_summary.json").exists()
    assert "dashboard_leakage_summary_json" in manifest["paths"]


def test_check_phase2_readiness_passes_on_synthetic_report(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_synthetic_jump_pilot(data_root)
    out = tmp_path / "phase2_report"
    run_phase2_local_report(data_root=data_root, out_dir=out, top_k=[1, 2], seed=7)

    result = check_phase2_readiness(out)

    assert result["ready_for_phase3"]
    assert result["n_failed"] == 0
    assert any(row["check"] == "diagnostics:controls" for row in result["checks"])


def test_check_phase2_readiness_cli_fails_when_artifacts_missing(tmp_path) -> None:
    missing_root = tmp_path / "missing"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_phase2_readiness.py",
            "--root",
            str(missing_root),
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert not payload["ready_for_phase3"]
    assert payload["n_failed"] > 0


def test_build_split_presets_cli_writes_held_out_plate_split(tmp_path) -> None:
    manifest = tmp_path / "site_manifest.csv"
    out = tmp_path / "split_manifest.csv"
    pd.DataFrame(
        {
            "dataset": ["rxrx1"] * 4,
            "site_id": ["s1", "s2", "s3", "s4"],
            "experiment": ["e1", "e1", "e2", "e2"],
            "plate": ["p1", "p1", "p2", "p2"],
            "well": ["A01", "A02", "A01", "A02"],
            "perturbation_id": ["a", "b", "c", "d"],
            "perturbation_name": ["A", "B", "C", "D"],
            "cell_type": ["cell"] * 4,
            "condition_label": ["control"] * 4,
            "concentration": ["1"] * 4,
        }
    ).to_csv(manifest, index=False)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_split_presets.py",
            "--manifest",
            str(manifest),
            "--preset",
            "held_out_plate",
            "--test-fraction",
            "0.5",
            "--out",
            str(out),
        ],
        check=True,
    )
    split_manifest = pd.read_csv(out)

    assert "test" in set(split_manifest["split"])
    assert split_manifest.groupby(["experiment", "plate"])["split"].nunique().max() == 1
    assert (tmp_path / "split_summary.csv").exists()
    assert (tmp_path / "split_summary.json").exists()
