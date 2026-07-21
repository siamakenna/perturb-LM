#!/usr/bin/env python3
"""Run the synthetic Phase 3C text-profile alignment smoke test."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.modeling.phase3c import run_synthetic_phase3c_alignment_smoke  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/phase3c_alignment_smoke"))
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = run_synthetic_phase3c_alignment_smoke(out_dir=args.out, seed=args.seed)
    summary = result["summary"]
    projection = summary[
        (summary["mode"] == "frozen_text_embeddings_linear_projection")
        & (summary["comparison"] == "point_estimate")
        & (summary["metric"] == "average_precision")
    ].iloc[0]
    tfidf = summary[
        (summary["mode"] == "identifier_stripped_tfidf")
        & (summary["comparison"] == "point_estimate")
        & (summary["metric"] == "average_precision")
    ].iloc[0]
    print("Phase 3C synthetic alignment smoke complete")
    print("Synthetic smoke is not biological evidence.")
    print(f"split: {result['split']}")
    print(f"retrieval_filter: {result['retrieval_filter']}")
    print(f"train_profiles: {result['train_profiles']}")
    print(f"test_profiles: {result['test_profiles']}")
    print(f"identifier_stripped_tfidf_mAP: {tfidf['estimate']:.4f}")
    print(f"linear_projection_mAP: {projection['estimate']:.4f}")
    print(f"summary: {args.out / 'phase3c_alignment_summary.csv'}")


if __name__ == "__main__":
    main()
