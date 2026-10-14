"""Deterministic CPJUMP1 source/cohort joins, with explicit unresolved records (#30)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np
import pandas as pd

BATCH = "2020_11_04_CPJUMP1"
REVISION = "56845c7d4dc322652952783d91dae0ffef47829f"
REPO = "jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1"
KIND = "normalized_feature_select_negcon_batch"
CONDITIONS = [
    "Perturbation",
    "Cell_type",
    "Time",
    "Density",
    "Antibiotics",
    "Cell_line",
    "Time_delay",
    "Times_imaged",
    "Anomaly",
]
MISSING = {"", "nan", "null", "<na>"}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in MISSING else text


def read_table(path: Path) -> pd.DataFrame:
    # Literal 'none' is meaningful for the source's Anomaly column.
    return pd.read_csv(
        path, sep="\t" if path.suffix in {".tsv", ".txt"} else ",", dtype=str, keep_default_na=False
    ).map(clean)


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def fetch_source(out: Path) -> None:
    """Download only a fixed small public metadata allowlist at an immutable revision."""
    import requests

    paths = [
        "benchmark/output/experiment-metadata.tsv",
        "README.md",
        "benchmark/0.create-experiment-metadata.ipynb",
        f"metadata/platemaps/{BATCH}/barcode_platemap.csv",
    ]
    for modality in ("compound", "crispr", "orf"):
        paths += [
            f"metadata/platemaps/{BATCH}/platemap/JUMP-Target-1_{modality}_platemap.txt",
            f"metadata/external_metadata/JUMP-Target-1_{modality}_metadata.tsv",
        ]
    paths += ["metadata/external_metadata/JUMP-Target-1_compound_metadata_targets.tsv"]
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for relative in paths:
        url = f"https://raw.githubusercontent.com/{REPO}/{REVISION}/{relative}"
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        data = bytearray()
        for block in response.iter_content(65536):
            data.extend(block)
            if len(data) > 1_000_000:
                raise ValueError("Source metadata exceeds the 1 MB per-file bound")
        target = out / Path(relative).name
        target.write_bytes(data)
        files.append({"path": relative, "url": url, "bytes": len(data), "sha256": checksum(target)})
    write_json(out / "provenance.json", {"revision": REVISION, "files": files})


def source_tables(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    experiments = read_table(root / "experiment-metadata.tsv")
    barcodes = read_table(root / "barcode_platemap.csv")
    barcodes["Batch"] = BATCH
    maps, annotations = [], []
    for modality in ("compound", "crispr", "orf"):
        name = f"JUMP-Target-1_{modality}_platemap"
        table = read_table(root / f"{name}.txt")
        table["Plate_Map_Name"] = name
        maps.append(table)
        table = read_table(root / f"JUMP-Target-1_{modality}_metadata.tsv")
        table["Perturbation"] = modality
        annotations.append(table)
    return (
        experiments,
        barcodes,
        pd.concat(maps, ignore_index=True).fillna(""),
        pd.concat(annotations, ignore_index=True).fillna(""),
    )


def load_profiles(root: Path, *, features: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """Select the explicit historical batch directory; never turn file count into plate count."""
    frames, files = [], []
    selected = root / "profiles" / BATCH
    for number, path in enumerate(sorted(selected.rglob(f"*{KIND}.csv.gz"))):
        frame = pd.read_csv(path, keep_default_na=False)
        numeric = [c for c in frame if c.startswith(("Cells_", "Cytoplasm_", "Nuclei_", "Image_"))]
        metadata = pd.read_csv(
            path, keep_default_na=False, dtype=str, usecols=lambda c: c.startswith("Metadata_")
        ).map(clean)
        metadata["audit_file"] = path.relative_to(root).as_posix()
        metadata["audit_row"] = np.arange(len(frame))
        metadata["record_id"] = [f"file{number:03d}:row{i:06d}" for i in range(len(frame))]
        metadata["path_batch"] = BATCH
        if features:
            metadata = pd.concat(
                [metadata, frame[numeric].apply(pd.to_numeric, errors="raise")], axis=1
            )
        frames.append(metadata)
        plates = sorted(set(metadata.get("Metadata_Plate", pd.Series(dtype=str))) - {""})
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": checksum(path),
                "rows": len(frame),
                "plates_observed_in_rows": plates,
                "feature_count": len(numeric),
                "feature_schema_sha256": hashlib.sha256("\n".join(numeric).encode()).hexdigest(),
            }
        )
    if not frames:
        return pd.DataFrame(), files
    return pd.concat(frames, ignore_index=True), files


def resolve_join(
    left: pd.DataFrame, right: pd.DataFrame, keys: list[str], fields: list[str], status: str
) -> pd.DataFrame:
    """No fan-out or first-match guessing: duplicate keys are ambiguous even if identical."""
    counts = right.groupby(keys, dropna=False).size().rename("_matches").reset_index()
    unique = right.loc[~right.duplicated(keys, keep=False), keys + fields]
    merged = left.merge(counts, on=keys, how="left", validate="many_to_one", sort=False)
    merged = merged.merge(unique, on=keys, how="left", validate="many_to_one", sort=False)
    merged[status] = np.select(
        [merged[keys].eq("").any(axis=1), merged._matches.gt(1), merged._matches.eq(1)],
        ["missing_key", "ambiguous", "matched"],
        default="unmatched",
    )
    return merged.drop(columns="_matches").fillna("")


def join_cohort(
    profiles: pd.DataFrame,
    experiments: pd.DataFrame,
    barcodes: pd.DataFrame,
    maps: pd.DataFrame,
    annotations: pd.DataFrame,
) -> pd.DataFrame:
    rows = profiles.copy()
    for name in ("Metadata_Plate", "Metadata_Well", "Metadata_broad_sample"):
        if name not in rows:
            rows[name] = ""
    explicit = rows.get(
        "Metadata_Batch", rows.get("Metadata_batch", pd.Series("", index=rows.index))
    )
    rows["Batch"] = explicit.where(explicit.ne(""), rows.get("path_batch", ""))
    rows["batch_evidence"] = np.where(explicit.ne(""), "profile_column", "path_inferred")
    rows["batch_path_conflict"] = explicit.ne("") & explicit.ne(rows.get("path_batch", ""))
    rows["Assay_Plate_Barcode"] = rows.Metadata_Plate
    fields = [c for c in experiments if c not in {"Batch", "Assay_Plate_Barcode"}]
    rows = resolve_join(
        rows, experiments, ["Batch", "Assay_Plate_Barcode"], fields, "experiment_status"
    )
    barcode = barcodes.rename(columns={"Plate_Map_Name": "barcode_map"})
    rows = resolve_join(
        rows, barcode, ["Batch", "Assay_Plate_Barcode"], ["barcode_map"], "barcode_status"
    )
    rows["map_conflict"] = rows.barcode_map.ne(rows.Plate_Map_Name)
    rows["well_position"] = rows.Metadata_Well.str.upper().str.replace(
        r"^([A-P])(\d)$", r"\g<1>0\2", regex=True
    )
    maps = maps.rename(columns={"broad_sample": "mapped_sample", "solvent": "mapped_solvent"})
    rows = resolve_join(
        rows,
        maps,
        ["Plate_Map_Name", "well_position"],
        [c for c in ("mapped_sample", "mapped_solvent") if c in maps],
        "well_status",
    )
    rows["sample_status"] = np.select(
        [
            rows.well_status.ne("matched"),
            rows.Metadata_broad_sample.eq(rows.mapped_sample),
            rows.Metadata_broad_sample.eq(""),
        ],
        ["unresolved_map", "matched", "missing_local"],
        default="conflict",
    )
    rows["broad_sample"] = rows.Metadata_broad_sample
    ann_fields = [c for c in annotations if c not in {"Perturbation", "broad_sample"}]
    rows = resolve_join(
        rows, annotations, ["Perturbation", "broad_sample"], ann_fields, "annotation_status"
    )
    rows["annotation_conflict"] = False
    rows["identity_annotation_conflict"] = False
    conflicts = []
    for field in ann_fields:
        local = "Metadata_" + field
        if local in rows:
            left, right = rows[local].map(clean), rows[field].map(clean)
            if field == "pubchem_cid":
                left, right = left.map(numeric_identifier), right.map(numeric_identifier)
            mismatch = left.ne(right) & rows.annotation_status.eq("matched")
            rows["annotation_conflict"] |= mismatch
            if field in {"gene", "pert_type", "control_type", "negcon_control_type"}:
                rows["identity_annotation_conflict"] |= mismatch
            conflicts.append((field, mismatch))
    rows["annotation_conflict_fields"] = [
        "|".join(field for field, mismatch in conflicts if mismatch.iloc[i])
        for i in range(len(rows))
    ]
    rows["duplicate_plate_well"] = rows.duplicated(
        ["Batch", "Assay_Plate_Barcode", "well_position"], keep=False
    )
    rows["resolved"] = (
        rows.experiment_status.eq("matched")
        & rows.barcode_status.eq("matched")
        & rows.well_status.eq("matched")
        & rows.sample_status.eq("matched")
        & ~rows.map_conflict
        & ~rows.batch_path_conflict
        & ~rows.identity_annotation_conflict
        & ~rows.duplicate_plate_well
        & (rows.annotation_status.eq("matched") | rows.broad_sample.eq(""))
    )
    return rows


def numeric_identifier(value: str) -> str:
    """Canonicalize equivalent numeric spellings, never round approximate identifiers."""
    try:
        return str(Decimal(value).normalize()) if value else ""
    except InvalidOperation:
        return value


def count_values(values: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in values.value_counts(dropna=False).sort_index().items()}


def replication(rows: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    labeled = rows[rows.resolved & rows.broad_sample.ne("")].copy()
    labeled["is_control"] = labeled.Metadata_pert_type.ne("trt")
    summaries = []
    for label, group in labeled.groupby("broad_sample", sort=True):
        cross_plate = cross_well = matched_condition = noncontrol = 0
        for _, row in group.iterrows():
            different_plate = group.Assay_Plate_Barcode.ne(row.Assay_Plate_Barcode)
            different_well = group.well_position.ne(row.well_position)
            same_conditions = group[CONDITIONS].eq(row[CONDITIONS]).all(axis=1)
            cross_plate += int(different_plate.any())
            cross_well += int((different_plate & different_well).any())
            matched_condition += int((different_plate & different_well & same_conditions).any())
            noncontrol += int(
                (different_plate & different_well & same_conditions).any() and not row.is_control
            )
        summaries.append(
            {
                "treatment": label,
                "rows": len(group),
                "plates": group.Assay_Plate_Barcode.nunique(),
                "well_coordinates": group.well_position.nunique(),
                "is_control": bool(group.is_control.any()),
                "cross_plate_evaluable_rows": cross_plate,
                "cross_plate_cross_well_evaluable_rows": cross_well,
                "condition_matched_evaluable_rows": matched_condition,
                "condition_matched_noncontrol_evaluable_rows": noncontrol,
            }
        )
    table = pd.DataFrame(summaries)
    summary = {"treatments": len(table)}
    if not table.empty:
        for c in table:
            if c.endswith("evaluable_rows"):
                summary[c] = int(table[c].sum())
                summary[c.replace("_rows", "_treatments")] = int(table[c].gt(0).sum())
        summary["treatments_multiple_plates"] = int(table.plates.gt(1).sum())
        summary["treatments_multiple_well_coordinates"] = int(table.well_coordinates.gt(1).sum())
        summary["noncontrol_treatments_multiple_well_coordinates"] = int(
            (table.well_coordinates.gt(1) & ~table.is_control).sum()
        )
    return summary, table


def target_overlap(rows: pd.DataFrame, target_annotations: pd.DataFrame) -> dict:
    """Count annotation intersections, never convert these into morphology positives."""
    local = rows[rows.resolved & rows.broad_sample.ne("")]
    compounds = set(local.loc[local.Perturbation.eq("compound"), "broad_sample"])
    crispr = local[local.Perturbation.eq("crispr") & local.Metadata_pert_type.eq("trt")]
    genes = set(crispr.Metadata_gene) - {""}
    a = target_annotations[target_annotations.broad_sample.isin(compounds)]
    sets = a.target_list.map(lambda x: set(clean(x).split("|")) - {""})
    principal = set(a.target) - {""}
    expanded = set().union(*sets) if len(sets) else set()
    time_matched = None
    if {"Cell_type", "Time"}.issubset(local.columns):
        candidate_pairs = []
        for _, annotation in a.iterrows():
            targets = (
                set(clean(annotation.target_list).split("|")) | {clean(annotation.target)}
            ) - {""}
            compound_rows = local[local.broad_sample.eq(annotation.broad_sample)]
            for cell, time in (
                compound_rows[["Cell_type", "Time"]].drop_duplicates().itertuples(index=False)
            ):
                matched = crispr[crispr.Cell_type.eq(cell) & crispr.Metadata_gene.isin(targets)]
                if len(matched) and time and matched.Time.ne("").all():
                    candidate_pairs.append(bool(matched.Time.eq(time).any()))
        if candidate_pairs:
            time_matched = any(candidate_pairs)
    return {
        "compound_annotation_rows": len(a),
        "crispr_genes": len(genes),
        "compound_unique_ids": a.broad_sample.nunique(),
        "duplicate_compound_annotation_rows": int(a.broad_sample.duplicated(keep=False).sum()),
        "multitarget_compound_rows": int(sets.map(len).gt(1).sum()),
        "shared_principal_genes": len(principal & genes),
        "shared_expanded_genes": len(expanded & genes),
        "compounds_with_expanded_crispr_match": int(sets.map(lambda x: bool(x & genes)).sum()),
        "compound_crispr_time_matched": time_matched,
        "interpretation": "Annotation overlap only; no approved biological relevance rule.",
    }


def cohort_audit(root: Path | None, source: Path, out: Path, *, features: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    experiments, barcodes, maps, annotations = source_tables(source)
    selected = experiments[experiments.Batch.eq(BATCH)]
    selected.to_csv(out / "source_plates.csv", index=False)
    selected.groupby(CONDITIONS, dropna=False).size().rename("plates").to_csv(
        out / "source_conditions.csv"
    )
    source_wells = selected.merge(maps, on="Plate_Map_Name", how="left")
    source_wells.to_csv(out / "source_plate_wells.csv", index=False)
    source_issues = selected.merge(
        barcodes,
        on=["Batch", "Assay_Plate_Barcode"],
        how="outer",
        suffixes=("_experiment", "_barcode"),
        indicator=True,
    )
    source_issues = source_issues[
        (source_issues._merge != "both")
        | (source_issues.Plate_Map_Name_experiment != source_issues.Plate_Map_Name_barcode)
    ]
    source_issues.to_csv(out / "source_inventory_discrepancies.csv", index=False)
    summary = {
        "batch": BATCH,
        "source_plate_count": len(selected),
        "source_modalities": count_values(selected.Perturbation),
        "source_cell_types": count_values(selected.Cell_type),
        "source_duplicate_plate_keys": int(
            selected.duplicated(["Batch", "Assay_Plate_Barcode"], keep=False).sum()
        ),
        "source_barcode_count": len(barcodes),
        "source_inventory_discrepancies": len(source_issues),
        "source_platemap_rows": count_values(maps.Plate_Map_Name),
        "source_duplicate_map_wells": int(
            maps.duplicated(["Plate_Map_Name", "well_position"], keep=False).sum()
        ),
        "source_annotation_rows": count_values(annotations.Perturbation),
        "source_duplicate_annotation_keys": int(
            annotations.duplicated(["Perturbation", "broad_sample"], keep=False).sum()
        ),
        "source_inventory_sanity_passed": len(selected) == 51
        and count_values(selected.Perturbation) == {"compound": 24, "crispr": 18, "orf": 9},
        "source_files": {
            p.name: checksum(p)
            for p in sorted(source.iterdir())
            if p.is_file() and p.name != "provenance.json"
        },
    }
    provenance = source / "provenance.json"
    if provenance.exists():
        manifest = json.loads(provenance.read_text())
        for entry in manifest["files"]:
            if checksum(source / Path(entry["path"]).name) != entry["sha256"]:
                raise ValueError("Source checksum differs from provenance manifest")
        summary["source_revision"] = manifest["revision"]
    else:
        summary["source_revision"] = "unverified user-supplied source files"
    profiles, files = load_profiles(root, features=features) if root else (pd.DataFrame(), [])
    write_json(out / "profile_manifest.json", files)
    if profiles.empty:
        summary["local_status"] = (
            "unavailable: expected profiles/<batch>/*/"
            "*normalized_feature_select_negcon_batch.csv.gz"
        )
        write_json(out / "cohort_summary.json", summary)
        return summary
    rows = join_cohort(profiles, experiments, barcodes, maps, annotations)
    feature_cols = [c for c in rows if c.startswith(("Cells_", "Cytoplasm_", "Nuclei_", "Image_"))]
    metadata = rows.drop(columns=feature_cols)
    metadata.to_csv(out / "local_mapping_PRIVATE.csv", index=False)
    metadata[~metadata.resolved | metadata.annotation_conflict].to_csv(
        out / "unresolved_PRIVATE.csv", index=False
    )
    metadata[metadata.broad_sample.eq("")].to_csv(
        out / "missing_treatment_PRIVATE.csv", index=False
    )
    summary.update(
        local_status="available",
        local_files=len(files),
        local_rows=len(rows),
        labeled_rows=int(rows.broad_sample.ne("").sum()),
        missing_treatment_rows=int(rows.broad_sample.eq("").sum()),
        resolved_rows=int(rows.resolved.sum()),
        unresolved_rows=int((~rows.resolved).sum()),
        annotation_conflict_rows=int(rows.annotation_conflict.sum()),
        annotation_conflict_fields=count_values(rows.annotation_conflict_fields),
        local_plate_count=rows.Assay_Plate_Barcode.nunique(),
        local_modalities=count_values(rows.Perturbation),
        local_cell_types=count_values(rows.Cell_type),
        local_anomalies=count_values(rows.Anomaly),
        local_batches=count_values(rows.Batch),
        query_categories=count_values(rows.Metadata_pert_type),
        batch_evidence=count_values(rows.batch_evidence),
    )
    for status in (
        "experiment_status",
        "barcode_status",
        "well_status",
        "sample_status",
        "annotation_status",
    ):
        summary[status] = count_values(rows[status])
    plates = (
        metadata.groupby(["Batch", "Assay_Plate_Barcode", *CONDITIONS], dropna=False)
        .agg(
            rows=("record_id", "size"),
            labeled=("broad_sample", lambda s: s.ne("").sum()),
            unique_wells=("well_position", "nunique"),
            resolved=("resolved", "sum"),
        )
        .reset_index()
    )
    plates.to_csv(out / "local_plates.csv", index=False)
    expected = source_wells[source_wells.Assay_Plate_Barcode.isin(rows.Assay_Plate_Barcode)]
    missing_wells = expected.merge(
        rows[["Batch", "Assay_Plate_Barcode", "well_position"]],
        on=["Batch", "Assay_Plate_Barcode", "well_position"],
        how="left",
        indicator=True,
    )
    missing_wells = missing_wells[missing_wells._merge.eq("left_only")]
    missing_wells.to_csv(out / "missing_wells_PRIVATE.csv", index=False)
    summary["absent_wells_from_included_plates"] = len(missing_wells)
    summary["target_overlap_by_cell_type"] = {
        cell: target_overlap(
            group, read_table(source / "JUMP-Target-1_compound_metadata_targets.tsv")
        )
        for cell, group in rows.groupby("Cell_type")
        if cell
    }

    metadata.groupby(
        [
            "Perturbation",
            "Metadata_pert_type",
            "Metadata_control_type",
            "Metadata_negcon_control_type",
        ],
        dropna=False,
    ).size().rename("rows").to_csv(out / "controls.csv")
    summary["replication"], replicates = replication(rows)
    replicates.to_csv(out / "replication_PRIVATE.csv", index=False)
    target_annotations = read_table(source / "JUMP-Target-1_compound_metadata_targets.tsv")
    target_annotations = target_annotations[
        target_annotations.broad_sample.isin(
            rows.loc[rows.Perturbation.eq("compound"), "broad_sample"]
        )
    ].copy()
    target_annotations["principal_absent_from_target_list"] = target_annotations.apply(
        lambda row: bool(row.target) and row.target not in row.target_list.split("|"), axis=1
    )
    target_annotations.to_csv(out / "compound_target_annotations_PRIVATE.csv", index=False)
    summary["principal_absent_from_target_list_compounds"] = int(
        target_annotations.principal_absent_from_target_list.sum()
    )
    summary["target_overlap"] = target_overlap(
        rows, read_table(source / "JUMP-Target-1_compound_metadata_targets.tsv")
    )
    write_json(out / "cohort_summary.json", summary)
    if features:
        pair_diagnostics(rows, feature_cols).to_csv(out / "plate_similarity.csv", index=False)
    return summary


def pair_diagnostics(rows: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Exhaustive descriptive cosine moments within culture strata; no retrieval scores.

    Existing negative-control-normalized features are used unchanged. No fit, bootstrap,
    inferential p-value, batch correction or benchmark modification is performed.
    """
    results = []
    for conditions, group in rows[rows.resolved & rows.broad_sample.ne("")].groupby(CONDITIONS):
        x = group[features].to_numpy(dtype=float)
        norms = np.linalg.norm(x, axis=1)
        valid = np.isfinite(x).all(axis=1) & (norms > 0)
        group = group.iloc[np.flatnonzero(valid)]
        x = x[valid] / norms[valid, None]
        plates, treatments, wells = (
            group[c].to_numpy() for c in ("Assay_Plate_Barcode", "broad_sample", "well_position")
        )
        totals = {}
        for i in range(len(x) - 1):
            scores = x[i + 1 :] @ x[i]
            for plate_same in (True, False):
                for treatment_same in (True, False):
                    mask = ((plates[i + 1 :] == plates[i]) == plate_same) & (
                        (treatments[i + 1 :] == treatments[i]) == treatment_same
                    )
                    # Also stratify position to expose fixed-layout confounding.
                    for well_same in (True, False):
                        values = scores[mask & ((wells[i + 1 :] == wells[i]) == well_same)]
                        key = plate_same, treatment_same, well_same
                        acc = totals.setdefault(key, [0, 0.0, 0.0])
                        acc[0] += len(values)
                        acc[1] += float(values.sum())
                        acc[2] += float((values**2).sum())
        for (sp, st, sw), (n, total, squares) in totals.items():
            if n:
                results.append(
                    dict(zip(CONDITIONS, conditions, strict=True))
                    | {
                        "same_plate": sp,
                        "same_treatment": st,
                        "same_well_coordinate": sw,
                        "pairs": n,
                        "mean_cosine": total / n,
                        "sd_cosine": max(0, squares / n - (total / n) ** 2) ** 0.5,
                        "excluded_nonfinite_or_zero_rows": int((~valid).sum()),
                    }
                )
    return pd.DataFrame(results)
