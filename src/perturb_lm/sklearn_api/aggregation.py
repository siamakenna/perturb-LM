"""Tidy, provenance-bearing result aggregation for synthetic and staged runs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.sklearn_api.datasets import file_checksum, present
from perturb_lm.sklearn_api.evaluation import QueryBootstrap


def aggregate_results(
    per_query: pd.DataFrame,
    *,
    exclusions: pd.DataFrame,
    provenance: dict,
    output: Path | str,
    baseline: pd.DataFrame | None = None,
    bootstrap: QueryBootstrap | None = None,
    metric: str = "average_precision",
) -> dict:
    """Write a complete result bundle atomically after validating all tables."""
    required = {"query_id", metric, "evaluable"}
    if not required <= set(per_query):
        raise ValueError(f"Per-query results missing: {sorted(required - set(per_query))}")
    if per_query.query_id.duplicated().any() or not per_query.query_id.map(present).all():
        raise ValueError("Aggregation requires one row per query ID")
    if not per_query.evaluable.map(lambda x: isinstance(x, (bool, np.bool_))).all():
        raise ValueError("evaluable must contain booleans")
    metrics = [
        key for key in per_query if key == metric or key.startswith(("hit_at_", "recall_at_"))
    ]
    if not np.isfinite(per_query.loc[per_query.evaluable, metrics].to_numpy(dtype=float)).all():
        raise ValueError("Evaluable query metrics must be finite")
    if not {"query_id", "reason"} <= set(exclusions):
        raise ValueError("Exclusions require query_id and machine-readable reason")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    working = output.with_name(output.name + ".working")
    if working.exists():
        raise ValueError("Incomplete aggregation directory exists; quarantine before retry")
    working.mkdir()
    try:
        per_query.to_csv(working / "per_query.csv", index=False)
        exclusions.to_csv(working / "exclusion_records.csv", index=False)
        exclusions.groupby("reason", dropna=False).size().rename("count").reset_index().to_csv(
            working / "exclusions.csv", index=False
        )
        evaluable = per_query.loc[per_query.evaluable]
        summary = {
            "n_queries": int(len(per_query)),
            "n_evaluable_queries": int(len(evaluable)),
            "n_excluded_queries": int((~per_query.evaluable).sum()),
            "metrics": {key: float(evaluable[key].mean()) for key in metrics if len(evaluable)},
            "provenance": provenance,
        }
        if baseline is not None:
            if baseline.query_id.duplicated().any() or not baseline.query_id.map(present).all():
                raise ValueError("Baseline requires one row per query ID")
            if set(per_query.query_id) != set(baseline.query_id):
                raise ValueError("Baseline and candidate query populations differ")
            paired = per_query.set_index("query_id").join(
                baseline.set_index("query_id"), lsuffix="", rsuffix="_baseline", how="inner"
            )
            eligible = (
                paired.evaluable
                & np.isfinite(paired[metric])
                & np.isfinite(paired[f"{metric}_baseline"])
            )
            if "evaluable_baseline" in paired:
                if not paired.evaluable_baseline.map(
                    lambda x: isinstance(x, (bool, np.bool_))
                ).all():
                    raise ValueError("Baseline evaluable must contain booleans")
                eligible &= paired.evaluable_baseline
            summary["n_evaluable_pairs"] = int(eligible.sum())
            summary["n_excluded_pairs"] = int((~eligible).sum())
            summary["paired_difference"] = (
                float(
                    (
                        paired.loc[eligible, metric] - paired.loc[eligible, f"{metric}_baseline"]
                    ).mean()
                )
                if eligible.any()
                else None
            )
            if bootstrap is not None and eligible.any():
                summary["paired_bootstrap"] = bootstrap.evaluate(per_query, baseline, metric=metric)
        (working / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        rows = [{"metric": key, "value": value} for key, value in summary["metrics"].items()]
        pd.DataFrame(rows).to_csv(working / "aggregate.csv", index=False)
        lines = [
            "# Benchmark result",
            "",
            f"- Queries: {summary['n_queries']}",
            f"- Evaluable queries: {summary['n_evaluable_queries']}",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        lines.extend(f"| {key} | {value:.6g} |" for key, value in summary["metrics"].items())
        (working / "candidate_table.md").write_text("\n".join(lines) + "\n")
        (working / "complete.json").write_text(
            json.dumps(
                {
                    "provenance": provenance,
                    "run_id": provenance.get("run_id"),
                    "output_checksums": {
                        path.name: file_checksum(path)
                        for path in working.iterdir()
                        if path.name != "complete.json"
                    },
                    "files": sorted(
                        path.name for path in working.iterdir() if path.name != "complete.json"
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        if output.exists():
            raise FileExistsError(f"Aggregation output already exists: {output}")
        working.rename(output)
    except BaseException:
        import shutil

        shutil.rmtree(working, ignore_errors=True)
        raise
    return summary
