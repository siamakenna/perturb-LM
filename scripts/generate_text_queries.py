#!/usr/bin/env python3
"""Generate auditable metadata-derived text queries for JUMP pilot profiles."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def nonempty(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip()
    return text != "" and text.lower() not in {"nan", "none", "null"}


def load_profile_metadata(manifest_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    frames = []
    for path in manifest["path"]:
        frame = pd.read_csv(path, usecols=lambda col: col.startswith("Metadata_"))
        frames.append(frame)
    metadata = pd.concat(frames, ignore_index=True)
    metadata = metadata.drop_duplicates()
    return metadata


def load_target_metadata(metadata_root: Path) -> pd.DataFrame:
    target_path = metadata_root / "JUMP-Target-1_compound_metadata_targets.tsv"
    if not target_path.exists():
        return pd.DataFrame()
    return pd.read_csv(target_path, sep="\t")


def first_existing_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in frame.columns:
            return column
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("data/interim/jump_pilot_profile_files.csv"))
    parser.add_argument("--metadata-root", type=Path, default=Path("data/raw/jump_pilot/metadata"))
    parser.add_argument("--out", type=Path, default=Path("data/interim/jump_pilot_queries.csv"))
    args = parser.parse_args()

    metadata = load_profile_metadata(args.manifest)
    targets = load_target_metadata(args.metadata_root)

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for _, row in metadata.iterrows():
        broad_sample = str(row.get("Metadata_broad_sample", "")).strip()
        pert_type = str(row.get("Metadata_pert_type", "")).strip()
        pert_name = str(row.get("Metadata_pert_iname", "")).strip()
        gene = str(row.get("Metadata_gene", "")).strip()

        if nonempty(broad_sample) and nonempty(pert_name):
            key = ("compound_name", broad_sample, pert_name)
            if key not in seen:
                rows.append(
                    {
                        "query_id": f"compound_name::{broad_sample}",
                        "query_text": f"cells treated with {pert_name}",
                        "target_label": broad_sample,
                        "target_name": pert_name,
                        "target_type": pert_type or "compound",
                        "label_column": "Metadata_broad_sample",
                    }
                )
                seen.add(key)

        if nonempty(gene):
            key = ("gene", gene, broad_sample)
            if key not in seen:
                rows.append(
                    {
                        "query_id": f"gene::{gene}::{broad_sample}",
                        "query_text": f"cells with perturbation of {gene}",
                        "target_label": broad_sample if nonempty(broad_sample) else gene,
                        "target_name": gene,
                        "target_type": pert_type or "gene",
                        "label_column": "Metadata_broad_sample" if nonempty(broad_sample) else "Metadata_gene",
                    }
                )
                seen.add(key)

    if not targets.empty:
        compound_col = first_existing_column(targets, ["pert_iname", "Metadata_pert_iname", "compound_name"])
        target_col = first_existing_column(targets, ["target", "Target", "Metadata_target", "gene", "Metadata_gene"])
        if compound_col and target_col:
            for _, row in targets.iterrows():
                compound = str(row.get(compound_col, "")).strip()
                target = str(row.get(target_col, "")).strip()
                if nonempty(compound) and nonempty(target):
                    key = ("compound_target", compound, target)
                    if key not in seen:
                        rows.append(
                            {
                                "query_id": f"compound_target::{compound}::{target}",
                                "query_text": f"cells treated with a compound targeting {target}",
                                "target_label": compound,
                                "target_name": target,
                                "target_type": "compound_target",
                                "label_column": "Metadata_pert_iname",
                            }
                        )
                        seen.add(key)

    queries = pd.DataFrame(rows).drop_duplicates()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    queries.to_csv(args.out, index=False)
    print(f"Wrote {len(queries)} queries to {args.out}")


if __name__ == "__main__":
    main()

