#!/usr/bin/env python3
"""Run metadata-derived text-to-profile retrieval for local JUMP profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.engineering.runtime import (  # noqa: E402
    PipelineRuntimeLogger,
    dashboard_safe_runtime_summary,
    write_runtime_log,
)
from perturb_lm.retrieval.text_profile import (  # noqa: E402
    run_text_profile_retrieval,
    run_text_profile_retrieval_multi_seed,
)


def load_queries(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--queries", type=Path, default=None)
    parser.add_argument("--label-column", default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--query-limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--out", type=Path, default=Path("outputs/jump_text_profile"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    queries = load_queries(args.queries)
    runtime = PipelineRuntimeLogger(
        dataset_track="jump_cpjump1_profiles",
        seed=args.seed if args.seeds is None else None,
    )
    if args.seeds is None:
        with runtime.stage("retrieval", seed=args.seed):
            per_query, hits, summary, metadata = run_text_profile_retrieval(
                args.data_root,
                queries=queries,
                label_column=args.label_column,
                max_rows=args.max_rows,
                query_limit=args.query_limit,
                top_k=args.top_k,
                seed=args.seed,
            )
        with runtime.stage("report_generation", seed=args.seed):
            query_rows = per_query[
                ["query_id", "query_text", "target_label", "label_column"]
            ].drop_duplicates()
            query_rows.to_csv(args.out / "jump_text_profile_queries.csv", index=False)
            per_query.to_csv(args.out / "jump_text_profile_per_query.csv", index=False)
            hits.to_csv(args.out / "jump_text_profile_top_hits.csv", index=False)
            summary.to_csv(args.out / "jump_text_profile_summary.csv", index=False)
            (args.out / "jump_text_profile_metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )
        print(summary.to_string(index=False))
    else:
        with runtime.stage("retrieval"):
            by_seed, aggregate, metadata = run_text_profile_retrieval_multi_seed(
                args.data_root,
                queries=queries,
                label_column=args.label_column,
                max_rows=args.max_rows,
                query_limit=args.query_limit,
                top_k=args.top_k,
                seeds=args.seeds,
                bootstrap_samples=args.bootstrap_samples,
            )
        with runtime.stage("report_generation"):
            by_seed.to_csv(args.out / "jump_text_profile_summary_by_seed.csv", index=False)
            aggregate.to_csv(args.out / "jump_text_profile_multiseed_summary.csv", index=False)
            (args.out / "jump_text_profile_multiseed_metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )
        print(aggregate.to_string(index=False))
    runtime_payload = runtime.finish(warnings=metadata["warnings"])
    write_runtime_log(args.out / "runtime_log.json", runtime_payload)
    write_runtime_log(
        args.out / "runtime_dashboard_safe.json",
        dashboard_safe_runtime_summary(runtime_payload),
    )
    print(f"Wrote JUMP text-to-profile retrieval outputs to {args.out}")


if __name__ == "__main__":
    main()
