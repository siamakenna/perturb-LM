#!/usr/bin/env python3
"""Build RxRx site and perturbation manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.rxrx_common import (
    SiteManifestStandardizationReport,
    find_metadata_files,
    make_perturbation_key,
    normalize_dataset,
    standardize_site_manifest_with_report,
)
from perturb_lm.schemas import (
    PERTURBATION_MANIFEST_COLUMNS,
    validate_perturbation_manifest,
    validate_site_manifest,
)


def find_metadata_file(dataset: str, data_root: Path) -> Path:
    candidates = find_metadata_files(dataset, data_root)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        f"No metadata file found for {dataset} under {data_root}. "
        "Expected CSV/TSV/parquet metadata; raw image archives are not required."
    )


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    return pd.read_csv(path)


def build_manifests(
    dataset: str,
    data_root: Path,
    out_dir: Path,
    *,
    return_report: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame] | tuple[pd.DataFrame, pd.DataFrame, SiteManifestStandardizationReport]:
    dataset = normalize_dataset(dataset)
    data_root = Path(data_root)
    out_dir = Path(out_dir)
    failures: list[str] = []
    for metadata_path in find_metadata_files(dataset, data_root):
        try:
            raw = read_table(metadata_path)
            site_manifest, report = standardize_site_manifest_with_report(
                dataset,
                raw,
                source_metadata_file=metadata_path,
            )
            break
        except Exception as exc:
            failures.append(f"{metadata_path}: {exc}")
    else:
        if failures:
            raise ValueError("Unable to build a site manifest from candidate metadata files. " + " | ".join(failures))
        raise FileNotFoundError(
            f"No metadata file found for {dataset} under {data_root}. "
            "Expected CSV/TSV/parquet metadata; raw image archives are not required."
        )
    perturbation_manifest = build_perturbation_manifest(site_manifest)
    write_outputs(dataset, site_manifest, perturbation_manifest, out_dir, report)
    if return_report:
        return site_manifest, perturbation_manifest, report
    return site_manifest, perturbation_manifest


def build_perturbation_manifest(site_manifest: pd.DataFrame) -> pd.DataFrame:
    validate_site_manifest(site_manifest)
    work = site_manifest.copy()
    work["perturbation_key"] = [
        make_perturbation_key(
            row.dataset,
            row.perturbation_id,
            row.perturbation_name,
            row.cell_type,
            row.condition_label,
            row.concentration,
        )
        for row in work.itertuples(index=False)
    ]
    work["_well_key"] = (
        work[["experiment", "plate", "well"]].fillna("").astype(str).agg("::".join, axis=1)
    )
    group_cols = [
        "dataset",
        "perturbation_key",
        "perturbation_id",
        "perturbation_name",
        "perturbation_type",
        "condition_label",
        "cell_type",
        "concentration",
    ]
    perturbation_manifest = (
        work.groupby(group_cols, dropna=False)
        .agg(
            n_sites=("site_id", "nunique"),
            n_wells=("_well_key", "nunique"),
            n_plates=("plate", "nunique"),
            n_experiments=("experiment", "nunique"),
        )
        .reset_index()
    )
    perturbation_manifest = perturbation_manifest[PERTURBATION_MANIFEST_COLUMNS]
    validate_perturbation_manifest(perturbation_manifest)
    return perturbation_manifest


def write_outputs(
    dataset: str,
    site_manifest: pd.DataFrame,
    perturbation_manifest: pd.DataFrame,
    out_dir: Path,
    report: SiteManifestStandardizationReport | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    site_csv = out_dir / f"{dataset}_site_manifest.csv"
    site_parquet = out_dir / f"{dataset}_site_manifest.parquet"
    perturb_csv = out_dir / f"{dataset}_perturbation_manifest.csv"
    perturb_parquet = out_dir / f"{dataset}_perturbation_manifest.parquet"
    site_manifest.to_csv(site_csv, index=False)
    site_manifest.to_parquet(site_parquet, index=False)
    perturbation_manifest.to_csv(perturb_csv, index=False)
    perturbation_manifest.to_parquet(perturb_parquet, index=False)
    print(f"Wrote {len(site_manifest)} site rows to {site_csv} and {site_parquet}")
    print(f"Wrote {len(perturbation_manifest)} perturbation rows to {perturb_csv} and {perturb_parquet}")
    if report is not None:
        report_path = out_dir / f"{dataset}_manifest_build_report.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
        print(f"Used metadata source: {report.source_metadata_file}")
        print(f"Wrote manifest build report to {report_path}")
        if report.optional_fields_missing:
            print("Optional source fields missing: " + ", ".join(report.optional_fields_missing))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--data-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    build_manifests(args.dataset, args.data_root, args.out)


if __name__ == "__main__":
    main()
