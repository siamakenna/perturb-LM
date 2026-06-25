from __future__ import annotations

import json

from scripts.run_phase2_jump_smoke import run_phase2_jump_smoke


def test_phase2_jump_smoke_runs_full_synthetic_pipeline(tmp_path) -> None:
    out_dir = tmp_path / "phase2_jump_smoke"

    summary = run_phase2_jump_smoke(out_dir)

    assert summary["audit_completed"]
    assert summary["number_of_rows_indexed"] == 6
    assert summary["number_of_numeric_feature_columns"] == 3
    assert "same_batch_at_1" in summary["diagnostics"]
    assert "same_plate_at_1" in summary["diagnostics"]
    assert "same_well_at_1" in summary["diagnostics"]
    assert "same_perturbation_treatment_at_1" in summary["diagnostics"]
    assert (out_dir / "jump_pilot_inventory.json").exists()
    assert (out_dir / "jump_pilot_index" / "index_metadata.json").exists()
    assert (
        out_dir
        / "jump_pilot_diagnostics"
        / "profile_neighbor_diagnostics_summary.csv"
    ).exists()
    smoke_summary = json.loads((out_dir / "smoke_summary.json").read_text())
    assert smoke_summary["synthetic_data_root"].replace("\\", "/").endswith(
        "synthetic_data/jump_pilot"
    )
