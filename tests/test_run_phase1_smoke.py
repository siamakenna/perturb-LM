from __future__ import annotations

import subprocess
import sys


def test_run_phase1_smoke_script(tmp_path) -> None:
    out = tmp_path / "phase1_smoke"
    subprocess.run(
        [sys.executable, "scripts/run_phase1_smoke.py", "--out", str(out)],
        check=True,
    )

    assert (out / "rxrx19a" / "processed" / "rxrx19a_site_manifest.csv").exists()
    assert (out / "rxrx19a" / "processed" / "rxrx19a_queries.csv").exists()
    assert (out / "rxrx19a" / "lexical" / "rxrx19a_site_retrieval_results.parquet").exists()
    assert (out / "rxrx19a" / "lexical" / "rxrx19a_perturbation_retrieval_results.parquet").exists()
    assert (out / "rxrx19a" / "lexical" / "eval" / "metrics_summary.csv").exists()
    assert (out / "phase1_report.md").exists()
