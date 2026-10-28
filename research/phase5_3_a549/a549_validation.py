"""Explicit source-bound A549 cohort checks, separate from the U2OS planner.

The physical-key, join, annotation, well, conflict, alias and control checks
are adapted from the reviewed rotations._validate implementation. Only this
new study's plate allowlist and expected conditions differ. The original
U2OS validator and its globals are never changed or monkeypatched.
"""

from __future__ import annotations

import pandas as pd
from perturb_lm.audits.cohort import BATCH, CONDITIONS, clean
from perturb_lm.audits.rotations import CONFLICTS, REQUIRED, _boolean, canonical_wells

PLATES = ("BR00117000", "BR00117003", "BR00117004", "BR00117005")

def validate_a549_mapping(mapping: pd.DataFrame) -> pd.DataFrame:
    if mapping.columns.duplicated().any():
        raise ValueError("Duplicate input column names")
    missing = sorted(set(REQUIRED) - set(mapping.columns))
    if missing:
        raise ValueError(f"Missing mapping columns: {', '.join(missing)}")
    rows = mapping.copy().map(clean)
    for field in ("record_id", "Batch", "Assay_Plate_Barcode", "well_position"):
        if rows[field].eq("").any():
            raise ValueError(f"Missing physical identity field: {field}")
    if rows.record_id.duplicated().any():
        raise ValueError("Duplicate record_id values")
    if rows.duplicated(["Batch", "Assay_Plate_Barcode", "well_position"]).any():
        raise ValueError("Duplicate physical plate/well records")
    if not rows.Assay_Plate_Barcode.isin(PLATES).all():
        raise ValueError("Input contains a plate outside the A549 allowlist")
    selected = rows.copy()
    if set(selected.Assay_Plate_Barcode) != set(PLATES):
        raise ValueError("All four prespecified A549 CRISPR plates must be represented")
    if not selected.Batch.eq(BATCH).all():
        raise ValueError("Selected plates have contradictory source batch assignments")
    if not selected.well_position.str.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])").all():
        raise ValueError("Well coordinates must be canonical A01 through P24")
    if selected[CONDITIONS].eq("").any().any():
        raise ValueError("Missing recorded culture/acquisition conditions")
    if len(selected[CONDITIONS].drop_duplicates()) != 1:
        raise ValueError("Selected plates contain mixed culture/acquisition conditions")
    first = selected.iloc[0]
    expected = {
        "Perturbation": "crispr",
        "Cell_type": "a549",
        "Time": "144",
        "Anomaly": "none",
        "Density": "100",
        "Time_delay": "day0",
        "Times_imaged": "1",
    }
    if any(first[key].casefold() != value for key, value in expected.items()):
        raise ValueError("Selected rows do not match the proposed A549 CRISPR 144 h no-recorded-anomaly stratum")
    if first.Cell_line.casefold() != "cas9" or first.Antibiotics.casefold() not in {
        "absent",
        "none",
    }:
        raise ValueError("Selected rows do not match Cas9 / absent-antibiotics conditions")
    if not selected.resolved.map(lambda x: _boolean(x, "resolved")).all():
        raise ValueError("Resolve ambiguous selected mappings before planning")
    for field in CONFLICTS:
        if selected[field].map(lambda x, field=field: _boolean(x, field)).any():
            raise ValueError(f"Selected mappings contain {field}")
    for field in ("experiment_status", "barcode_status", "well_status", "sample_status"):
        if not selected[field].eq("matched").all():
            raise ValueError(f"Selected mappings contain ambiguous/nonmatched {field}")
    labeled = selected.broad_sample.ne("")
    if not selected.loc[labeled, "annotation_status"].eq("matched").all():
        raise ValueError("Labeled selected rows require matched annotations")
    if selected.loc[labeled, "Metadata_pert_type"].eq("").any():
        raise ValueError("Labeled selected rows require a treatment/control category")
    # 'trt' is the unchanged audit definition of non-control; never parse booleans by truthiness.
    derived_control = selected.Metadata_pert_type.ne("trt")
    if "is_control" in selected:
        supplied = selected.is_control.map(lambda x: _boolean(x, "is_control"))
        if not supplied.loc[labeled].eq(derived_control.loc[labeled]).all():
            raise ValueError("is_control contradicts the audited treatment/control category")
    selected["is_control"] = derived_control
    for alias, canonical in (
        ("Metadata_broad_sample", "broad_sample"),
        ("mapped_sample", "broad_sample"),
        ("Metadata_Plate", "Assay_Plate_Barcode"),
        ("gene", "Metadata_gene"),
        ("pert_type", "Metadata_pert_type"),
        ("control_type", "Metadata_control_type"),
        ("negcon_control_type", "Metadata_negcon_control_type"),
    ):
        if alias in selected and canonical in selected:
            if not selected[alias].eq(selected[canonical]).all():
                raise ValueError(f"Contradictory selected identity annotation: {alias}")
    if "Metadata_Well" in selected:
        original_wells = canonical_wells(selected.Metadata_Well)
        if not original_wells.eq(selected.well_position).all():
            raise ValueError("Contradictory selected identity annotation: Metadata_Well")
    for alias in ("Metadata_Batch", "Metadata_batch", "path_batch"):
        if (
            alias in selected
            and (selected[alias].ne("") & selected[alias].ne(selected.Batch)).any()
        ):
            raise ValueError(f"Contradictory selected identity annotation: {alias}")
    for _, group in selected[labeled].groupby("broad_sample"):
        if group.Metadata_gene.nunique() > 1 or group.is_control.nunique() > 1:
            raise ValueError("A reagent has inconsistent gene or control annotations")
    return selected.sort_values("record_id").reset_index(drop=True)

