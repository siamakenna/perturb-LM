from __future__ import annotations

import subprocess
import sys

import pandas as pd

from perturb_lm.reports import make_rxrx_readiness_report


def test_make_rxrx_readiness_report_summarizes_available_artifacts(tmp_path) -> None:
    inventory = {
        "dataset": "rxrx1",
        "data_root": "data/raw",
        "metadata_files": ["data/raw/rxrx1/metadata.csv"],
        "embedding_files": ["data/raw/rxrx1/embeddings.csv"],
        "image_file_counts": {".png": 2},
        "manifest_rows_checked": 1,
        "manifest_image_paths_checked": 2,
        "manifest_image_paths_found": 1,
        "manifest_image_paths_missing": 1,
        "missing_manifest_examples": ["data/raw/rxrx1/missing.png"],
    }
    manifest_report = {
        "source_metadata_file": "data/raw/rxrx1/metadata.csv",
        "n_raw_rows": 2,
        "column_mappings": {"experiment": "Metadata_Experiment"},
        "optional_fields_missing": ["concentration"],
        "required_fields_missing": [],
    }
    index_metadata = {
        "dataset": "rxrx1",
        "backend": "sklearn-nearest-neighbors",
        "metric": "cosine",
        "n_embeddings_loaded": 2,
        "embedding_dimension": 3,
        "n_matched_to_manifest": 2,
        "n_unmatched": 0,
    }
    leakage = pd.DataFrame(
        [
            {"metric": "n_queries", "value": 4},
            {"metric": "queries_with_positive_cross_batch", "value": 1},
        ]
    )
    composites = pd.DataFrame(
        [
            {"site_id": "s1", "composite_status": "rendered"},
            {"site_id": "s2", "composite_status": "missing_channels"},
        ]
    )

    out = make_rxrx_readiness_report(
        dataset="rxrx1",
        inventory=inventory,
        manifest_build_report=manifest_report,
        index_metadata=index_metadata,
        leakage_summary=leakage,
        composite_manifest=composites,
        out_path=tmp_path / "report.md",
    )

    text = out.read_text()
    assert "RxRx Phase 2 Readiness Report: rxrx1" in text
    assert "local metadata discovered" in text
    assert "data/raw/rxrx1/metadata.csv" in text
    assert "Composite Rendering Summary" in text
    assert "It does not mean natural-language biological retrieval has been demonstrated" in text


def test_make_rxrx_readiness_report_cli_audits_when_inventory_missing(tmp_path) -> None:
    data_root = tmp_path / "raw"
    rxrx1 = data_root / "rxrx1"
    rxrx1.mkdir(parents=True)
    (rxrx1 / "metadata.csv").write_text("experiment,plate,well,sirna_id\nexp1,p1,A01,s1\n")
    out = tmp_path / "readiness.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/make_rxrx_readiness_report.py",
            "--dataset",
            "rxrx1",
            "--data-root",
            str(data_root),
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = out.read_text()
    assert "RxRx Phase 2 Readiness Report: rxrx1" in payload
    assert str(rxrx1 / "metadata.csv") in payload
