#!/usr/bin/env python3
"""Run the synthetic Phase 3B linear-projection contract smoke test."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.modeling.linear_projection import run_synthetic_projection_contract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/phase3b_projection_smoke"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--random-fixture", action="store_true")
    args = parser.parse_args()

    summary = run_synthetic_projection_contract(
        out_dir=args.out,
        seed=args.seed,
        learnable=not args.random_fixture,
    )
    print("Phase 3B synthetic projection smoke complete")
    print(f"train_rows: {summary['train_rows']}")
    print(f"test_rows: {summary['test_rows']}")
    print(
        "projection_mAP: "
        f"{summary['projection']['mean_average_precision']:.4f}"
    )
    print(f"summary: {args.out / 'phase3b_projection_smoke_summary.json'}")


if __name__ == "__main__":
    main()
