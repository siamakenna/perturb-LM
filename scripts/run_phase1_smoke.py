#!/usr/bin/env python3
"""Run an end-to-end Phase 1 smoke test on tiny fixtures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.queries.build_queries import build_queries
from perturb_lm.reports import make_phase1_report
from perturb_lm.retrieval.metrics import evaluate_perturbation_retrieval
from perturb_lm.retrieval.search import run_retrieval, write_retrieval_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("outputs/phase1_smoke"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    fixture_root = ROOT / "tests" / "fixtures"
    final_report = None

    for dataset in ["rxrx1", "rxrx19a"]:
        dataset_out = args.out / dataset
        processed = dataset_out / "processed"
        site_manifest, perturbation_manifest = build_manifests(dataset, fixture_root, processed)
        queries = build_queries(dataset, perturbation_manifest)
        query_path = processed / f"{dataset}_queries.csv"
        queries.to_csv(query_path, index=False)

        for mode in ["random", "shuffled", "lexical"]:
            run_out = dataset_out / mode
            site_results, perturbation_results = run_retrieval(
                queries,
                site_manifest,
                dataset=dataset,
                mode=mode,
                top_k=10,
                seed=13,
            )
            paths = write_retrieval_outputs(dataset, site_results, perturbation_results, run_out)
            metrics, per_query = evaluate_perturbation_retrieval(
                perturbation_results,
                queries,
                site_results=site_results,
                top_k=[1, 5, 10],
            )
            eval_out = run_out / "eval"
            eval_out.mkdir(parents=True, exist_ok=True)
            metrics.to_csv(eval_out / "metrics_summary.csv", index=False)
            per_query.to_csv(eval_out / "per_query_metrics.csv", index=False)
            (eval_out / "metrics_summary.json").write_text(
                metrics.set_index("metric")["value"].to_json(indent=2) + "\n"
            )
            report = make_phase1_report(
                dataset=dataset,
                queries=queries,
                site_manifest=site_manifest,
                perturbation_results=perturbation_results,
                metrics=metrics,
                out_path=run_out / "phase1_report.md",
                mode=mode,
                fixture=True,
            )
            if dataset == "rxrx19a" and mode == "lexical":
                final_report = report
            print(f"{dataset} {mode}: wrote {paths['site_csv']} and metrics to {eval_out}")

    if final_report is not None:
        (args.out / "phase1_report.md").write_text(final_report.read_text())
    print(f"Phase 1 smoke test complete: {args.out}")


if __name__ == "__main__":
    main()
