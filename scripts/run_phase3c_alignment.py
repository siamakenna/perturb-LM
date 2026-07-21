#!/usr/bin/env python3
"""Run one local Phase 3C text-to-morphology alignment condition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    add_jump_profile_ids,
    detect_jump_profile_schema,
    load_jump_profile_tables,
)
from perturb_lm.modeling.phase3c import (  # noqa: E402
    run_phase3c_alignment,
    write_phase3c_public_safe_summary,
)
from perturb_lm.modeling.preprocessing import _validate_ignored_output_path  # noqa: E402
from perturb_lm.modeling.text_encoder import (  # noqa: E402
    BIOMEDBERT_SPEC,
    DeterministicFakeTextEncoder,
    FrozenBiomedicalTextEncoder,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--profile-file", type=Path, action="append", default=None)
    parser.add_argument("--out", type=Path, default=Path("outputs/phase3c/alignment"))
    parser.add_argument("--label-column", default=None)
    parser.add_argument("--split", choices=["held_out_plate", "held_out_treatment", "held_out_well"], default="held_out_plate")
    parser.add_argument(
        "--retrieval-filter",
        choices=["none", "exclude_same_plate", "exclude_same_well", "exclude_same_plate_and_well"],
        default="none",
    )
    parser.add_argument("--encoder", choices=["fake", "biomedbert"], default="fake")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bootstrap-samples", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    _validate_ignored_output_path(args.out)
    profiles, _, warnings = load_jump_profile_tables(
        args.data_root,
        profile_files=args.profile_file,
        max_rows=args.max_rows,
    )
    schema = detect_jump_profile_schema(profiles)
    indexed = add_jump_profile_ids(profiles, schema)
    label_column = args.label_column or (
        schema["likely_perturbation_treatment_columns"][0]
        if schema["likely_perturbation_treatment_columns"]
        else None
    )
    if not label_column:
        raise ValueError("No treatment label column was detected.")
    rename_map = {
        label_column: "treatment",
        schema["likely_plate_column"]: "plate",
        schema["likely_well_column"]: "well",
        schema["likely_batch_column"]: "batch",
    }
    normalized = indexed.rename(
        columns={source: target for source, target in rename_map.items() if source}
    )
    if "batch" not in normalized.columns:
        normalized["batch"] = "unavailable"
    if args.encoder == "fake":
        encoder = DeterministicFakeTextEncoder(seed=args.seed, embedding_dimension_value=16)
        encoder_payload = {"model_name": "deterministic_fake_text_encoder"}
    else:
        encoder = FrozenBiomedicalTextEncoder(
            batch_size=args.batch_size,
            device=args.device,
            cache_dir=args.cache_dir,
        )
        encoder_payload = BIOMEDBERT_SPEC.__dict__
    result = run_phase3c_alignment(
        normalized,
        encoder=encoder,
        split_type=args.split,
        retrieval_filter=args.retrieval_filter,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
    )
    result["warnings"] = [*warnings, *result.get("warnings", [])]
    write_phase3c_public_safe_summary(result, args.out)
    payload = {
        "split": result["split"],
        "retrieval_filter": result["retrieval_filter"],
        "status": result["status"],
        "seed": result["seed"],
        "encoder": encoder_payload,
        "aggregate_summary_path": "phase3c_alignment_summary.csv",
        "public_manifest_path": "phase3c_public_safe_manifest.json",
        "artifact_policy": "Full generated outputs stay local and ignored.",
    }
    (args.out / "phase3c_run_manifest_public_safe.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(result["summary"].to_string(index=False))
    print(f"Wrote aggregate Phase 3C outputs to {args.out}")


if __name__ == "__main__":
    main()
