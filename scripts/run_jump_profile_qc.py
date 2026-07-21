#!/usr/bin/env python3
"""Run aggregate QC for local JUMP morphology profile tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.profile_qc import (  # noqa: E402
    ProfileQcOptions,
    dashboard_safe_profile_qc_summary,
    run_jump_profile_qc,
    write_profile_qc_outputs,
)
from perturb_lm.engineering.runtime import (  # noqa: E402
    PipelineRuntimeLogger,
    dashboard_safe_runtime_summary,
    write_runtime_log,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--profile-file", type=Path, action="append", default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--near-zero-variance-threshold", type=float, default=1e-12)
    parser.add_argument("--extreme-value-threshold", type=float, default=1e6)
    parser.add_argument(
        "--harmonization-policy",
        choices=["strict_intersection", "primary_schema_only", "explicit_feature_map"],
        default="strict_intersection",
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/jump_profile_qc"))
    args = parser.parse_args()

    runtime = PipelineRuntimeLogger(dataset_track="jump_cpjump1_profiles")
    with runtime.stage("feature_qc"):
        report = run_jump_profile_qc(
            args.data_root,
            profile_files=args.profile_file,
            max_rows=args.max_rows,
            options=ProfileQcOptions(
                near_zero_variance_threshold=args.near_zero_variance_threshold,
                extreme_value_threshold=args.extreme_value_threshold,
                harmonization_policy=args.harmonization_policy,
            ),
        )
    with runtime.stage("report_generation"):
        outputs = write_profile_qc_outputs(report, args.out)
    runtime_payload = runtime.finish(warnings=report["warnings"])
    runtime_path = args.out / "runtime_log.json"
    dashboard_runtime_path = args.out / "runtime_dashboard_safe.json"
    write_runtime_log(runtime_path, runtime_payload)
    write_runtime_log(dashboard_runtime_path, dashboard_safe_runtime_summary(runtime_payload))
    safe = dashboard_safe_profile_qc_summary(report)

    print("JUMP profile QC complete")
    print(f"profile_file_count: {safe['profile_file_count']}")
    print(f"total_profile_rows: {safe['total_profile_rows']}")
    print(
        "intersection_numeric_morphology_feature_count: "
        f"{safe['intersection_numeric_morphology_feature_count']}"
    )
    print(
        "usable_numeric_morphology_column_count: "
        f"{safe['usable_numeric_morphology_column_count']}"
    )
    if safe["warnings"]:
        print("warnings:")
        for warning in safe["warnings"]:
            print(f"- {warning}")
    print(f"Wrote aggregate QC outputs to {args.out}")
    print(f"Dashboard-safe JSON: {outputs['dashboard_safe_json']}")
    print(f"Runtime log: {runtime_path}")


if __name__ == "__main__":
    main()
