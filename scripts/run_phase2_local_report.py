#!/usr/bin/env python3
"""Run the local Phase 2 JUMP baseline pipeline and build one report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    audit_jump_pilot,
    build_jump_profile_index,
    run_jump_profile_diagnostics,
)
from perturb_lm.reports import make_phase2_jump_report  # noqa: E402
from perturb_lm.retrieval.text_profile import run_text_profile_retrieval  # noqa: E402


def run_phase2_local_report(
    *,
    data_root: Path | str,
    out_dir: Path | str,
    max_rows: int | None = None,
    top_k: list[int] | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Run audit, index, diagnostics, text baseline, report, and manifest."""

    data_root = Path(data_root)
    out_dir = Path(out_dir)
    top_k = sorted(set(top_k or [1, 5, 10]))
    index_dir = out_dir / "index"
    diagnostics_dir = out_dir / "diagnostics"
    text_dir = out_dir / "text_profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = audit_jump_pilot(data_root)
    inventory_path = out_dir / "inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")

    index_metadata = build_jump_profile_index(
        data_root,
        out_dir=index_dir,
        max_rows=max_rows,
    )
    index_metadata_path = index_dir / "index_metadata.json"

    per_query, diagnostics_summary, diagnostics_metadata = run_jump_profile_diagnostics(
        data_root,
        top_k=top_k,
        max_rows=max_rows,
        seed=seed,
        filtered_presets=True,
    )
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_per_query_path = diagnostics_dir / "profile_neighbor_diagnostics.csv"
    diagnostics_summary_path = diagnostics_dir / "profile_neighbor_diagnostics_summary.csv"
    diagnostics_json_path = diagnostics_dir / "profile_neighbor_diagnostics_summary.json"
    per_query.to_csv(diagnostics_per_query_path, index=False)
    diagnostics_summary.to_csv(diagnostics_summary_path, index=False)
    diagnostics_json_path.write_text(
        json.dumps(
            {
                "metadata": diagnostics_metadata,
                "summary": diagnostics_summary.to_dict(orient="records"),
            },
            indent=2,
        )
        + "\n"
    )

    text_per_query, text_hits, text_summary, text_metadata = run_text_profile_retrieval(
        data_root,
        max_rows=max_rows,
        top_k=top_k,
        seed=seed,
    )
    text_dir.mkdir(parents=True, exist_ok=True)
    text_queries = text_per_query[
        ["query_id", "query_text", "target_label", "label_column"]
    ].drop_duplicates()
    text_queries_path = text_dir / "jump_text_profile_queries.csv"
    text_per_query_path = text_dir / "jump_text_profile_per_query.csv"
    text_hits_path = text_dir / "jump_text_profile_top_hits.csv"
    text_summary_path = text_dir / "jump_text_profile_summary.csv"
    text_metadata_path = text_dir / "jump_text_profile_metadata.json"
    text_queries.to_csv(text_queries_path, index=False)
    text_per_query.to_csv(text_per_query_path, index=False)
    text_hits.to_csv(text_hits_path, index=False)
    text_summary.to_csv(text_summary_path, index=False)
    text_metadata_path.write_text(json.dumps(text_metadata, indent=2) + "\n")

    report_path = make_phase2_jump_report(
        inventory=inventory,
        index_metadata=index_metadata,
        diagnostics_summary=diagnostics_summary,
        diagnostics_metadata=diagnostics_metadata,
        text_profile_summary=text_summary,
        out_path=out_dir / "phase2_jump_report.md",
    )
    manifest = _baseline_manifest(
        data_root=data_root,
        out_dir=out_dir,
        max_rows=max_rows,
        top_k=top_k,
        seed=seed,
        inventory=inventory,
        index_metadata=index_metadata,
        diagnostics_metadata=diagnostics_metadata,
        text_metadata=text_metadata,
        paths={
            "inventory": inventory_path,
            "index_metadata": index_metadata_path,
            "diagnostics_summary": diagnostics_summary_path,
            "diagnostics_json": diagnostics_json_path,
            "text_profile_summary": text_summary_path,
            "text_profile_metadata": text_metadata_path,
            "report": report_path,
        },
    )
    manifest_path = out_dir / "baseline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["paths"]["baseline_manifest"] = str(manifest_path)
    return manifest


def _baseline_manifest(
    *,
    data_root: Path,
    out_dir: Path,
    max_rows: int | None,
    top_k: list[int],
    seed: int,
    inventory: dict[str, Any],
    index_metadata: dict[str, Any],
    diagnostics_metadata: dict[str, Any],
    text_metadata: dict[str, Any],
    paths: dict[str, Path],
) -> dict[str, Any]:
    return {
        "phase": "phase2",
        "dataset_track": "JUMP CPJUMP1 profiles",
        "data_root": str(data_root),
        "output_directory": str(out_dir),
        "max_rows": max_rows,
        "top_k": top_k,
        "seed": seed,
        "profile_files_found": len(inventory.get("profile_files_found", [])),
        "metadata_files_found": len(inventory.get("metadata_files_found", [])),
        "indexed_profile_rows": index_metadata.get("number_of_rows"),
        "numeric_feature_columns": index_metadata.get("number_of_numeric_feature_columns"),
        "batch_column": index_metadata.get("detected_batch_column"),
        "plate_column": index_metadata.get("detected_plate_column"),
        "well_column": index_metadata.get("detected_well_column"),
        "treatment_columns": index_metadata.get("detected_perturbation_treatment_columns", []),
        "diagnostic_modes": diagnostics_metadata.get("diagnostic_columns", []),
        "diagnostic_filters": diagnostics_metadata.get("filters", []),
        "text_profile_modes": text_metadata.get("modes", []),
        "text_profile_label_column": text_metadata.get("label_column"),
        "text_profile_queries": text_metadata.get("number_of_queries"),
        "known_limitations": [
            "This is parser/profile/text-control validation, not a biological retrieval claim.",
            "Same-batch diagnostics are not informative when only one batch is present.",
            "Full metadata TF-IDF includes direct perturbation identifiers.",
            "Generated outputs should remain outside git.",
        ],
        "paths": {key: str(path) for key, path in paths.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--out", type=Path, default=Path("outputs/jump_pilot_real_baseline"))
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    manifest = run_phase2_local_report(
        data_root=args.data_root,
        out_dir=args.out,
        max_rows=args.max_rows,
        top_k=args.top_k,
        seed=args.seed,
    )
    print(f"Wrote Phase 2 local report to {manifest['paths']['report']}")
    print(f"Wrote baseline manifest to {manifest['paths']['baseline_manifest']}")


if __name__ == "__main__":
    main()
