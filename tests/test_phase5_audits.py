"""Synthetic regression fixtures only: no pretrained models or scientific performance."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from perturb_lm.audits.cohort import (
    BATCH,
    KIND,
    join_cohort,
    load_profiles,
    pair_diagnostics,
    read_table,
    replication,
    resolve_join,
    target_overlap,
)
from perturb_lm.audits.queries import audit_queries, query_counts, render_queries

FIXTURES = Path(__file__).parent / "fixtures" / "phase5"


@pytest.fixture
def inputs():
    profiles = read_table(FIXTURES / "profiles.csv")
    experiment = read_table(FIXTURES / "experiment.tsv")
    barcode = experiment[["Batch", "Assay_Plate_Barcode", "Plate_Map_Name"]].copy()
    maps = pd.DataFrame(
        {
            "Plate_Map_Name": ["synthetic_map"] * 2,
            "well_position": ["A01", "A02"],
            "broad_sample": ["SYNTH_TREAT_A", "SYNTH_TREAT_B"],
        }
    )
    annotations = pd.DataFrame(
        {
            "Perturbation": ["compound"] * 2,
            "broad_sample": ["SYNTH_TREAT_A", "SYNTH_TREAT_B"],
            "gene": ["SYNTH_GENE_A", "SYNTH_GENE_B"],
            "pert_type": ["trt"] * 2,
        }
    )
    return profiles, experiment, barcode, maps, annotations


def test_complete_join_and_no_cross_well_positives(inputs):
    joined = join_cohort(*inputs)
    assert len(joined) == 4 and joined.resolved.all()
    summary, _ = replication(joined)
    assert summary["cross_plate_evaluable_rows"] == 4
    assert summary["cross_plate_cross_well_evaluable_rows"] == 0


def test_duplicate_source_key_is_ambiguous_without_fanout(inputs):
    p, e, b, m, a = inputs
    e = pd.concat([e, e.iloc[:1]])
    joined = join_cohort(p, e, b, m, a)
    assert len(joined) == 4
    assert joined.experiment_status.eq("ambiguous").sum() == 2
    assert joined.resolved.sum() == 2


@pytest.mark.parametrize(
    "kind",
    [
        "missing_plate",
        "unknown_plate",
        "missing_well",
        "unknown_well",
        "wrong_treatment",
        "wrong_batch",
        "wrong_gene",
        "wrong_barcode_map",
        "duplicate_well_map",
    ],
)
def test_unresolved_records_are_not_silently_used(inputs, kind):
    p, e, b, m, a = inputs
    if kind == "missing_plate":
        p.loc[0, "Metadata_Plate"] = ""
    elif kind == "unknown_plate":
        p.loc[0, "Metadata_Plate"] = "SYNTH_UNKNOWN"
    elif kind == "missing_well":
        p.loc[0, "Metadata_Well"] = ""
    elif kind == "unknown_well":
        p.loc[0, "Metadata_Well"] = "P24"
    elif kind == "wrong_treatment":
        p.loc[0, "Metadata_broad_sample"] = "SYNTH_OTHER"
    elif kind == "wrong_batch":
        p.loc[0, "Metadata_Batch"] = "other_batch"
        p["Metadata_Batch"] = p.Metadata_Batch.fillna("")
    elif kind == "wrong_gene":
        p.loc[0, "Metadata_gene"] = "SYNTH_OTHER"
    elif kind == "wrong_barcode_map":
        b.loc[0, "Plate_Map_Name"] = "wrong_map"
    else:
        m = pd.concat([m, m.iloc[:1]])
    joined = join_cohort(p, e, b, m, a)
    assert len(joined) == 4
    assert not joined.iloc[0].resolved


def test_duplicate_local_plate_well_quarantined(inputs):
    p, e, b, m, a = inputs
    joined = join_cohort(pd.concat([p, p.iloc[:1]]), e, b, m, a)
    assert joined.duplicate_plate_well.sum() == 2
    assert joined.resolved.sum() == 3


def test_missing_treatment_matching_blank_map_not_fabricated(inputs):
    p, e, b, m, a = inputs
    p.loc[[0, 1], "Metadata_broad_sample"] = ""
    m.loc[0, "broad_sample"] = ""
    joined = join_cohort(p, e, b, m, a)
    assert joined.resolved.all()
    assert joined.annotation_status.eq("missing_key").sum() == 2
    assert replication(joined)[0]["treatments"] == 1


def test_resolve_join_missing_keys_never_match():
    result = resolve_join(
        pd.DataFrame({"k": [""]}), pd.DataFrame({"k": [""], "v": ["x"]}), ["k"], ["v"], "status"
    )
    assert result.status.tolist() == ["missing_key"]


def test_file_may_contain_many_plates_and_second_batch_excluded(tmp_path, inputs):
    p = inputs[0].drop(columns=["record_id", "path_batch"])
    p["Cells_Synthetic"] = [1, 2, 3, 4]
    for batch in (BATCH, "2020_11_18_CPJUMP1_TimepointDay1"):
        directory = tmp_path / "profiles" / batch / "arbitrary_filename"
        directory.mkdir(parents=True)
        p.to_csv(directory / f"bundle_{KIND}.csv.gz", index=False)
    rows, files = load_profiles(tmp_path)
    assert len(files) == 1 and len(rows) == 4
    assert files[0]["plates_observed_in_rows"] == ["SYNTH_PLATE_A", "SYNTH_PLATE_B"]
    assert files[0]["feature_count"] == 1
    assert "Cells_Synthetic" not in rows


def test_missing_local_data(tmp_path):
    rows, files = load_profiles(tmp_path)
    assert rows.empty and files == []


def test_replication_respects_antibiotics(inputs):
    p, e, b, m, a = inputs
    # Replicate same treatment at different positions on separate plates.
    p.loc[1, "Metadata_Well"] = "A03"
    m = pd.concat([m, m.iloc[:1].assign(well_position="A03")])
    joined = join_cohort(p, e, b, m, a)
    assert replication(joined)[0]["condition_matched_noncontrol_evaluable_rows"] == 2
    e.loc[1, "Antibiotics"] = "Puromycin"
    joined = join_cohort(p, e, b, m, a)
    assert replication(joined)[0]["condition_matched_noncontrol_evaluable_rows"] == 0


def test_v2_collision_and_historical_distinction(inputs):
    result, _ = audit_queries(inputs[0])
    assert result["M0_IDENTITY_FREE_V2"]["unique_strings"] == 1
    assert result["M0_IDENTITY_FREE_V2"]["queries_in_collisions"] == 4
    assert result["M0_IDENTITY_FREE_V2"]["generic_category_fraction"] == 1
    assert result["M0_GENE_AWARE_V1"]["unique_strings"] == 2
    assert result["M0_GENE_AWARE_V1"]["matches_historical_treatment_renderer"]


def test_counts_deterministic_under_row_shuffle(inputs):
    a, groups_a = audit_queries(inputs[0])
    b, groups_b = audit_queries(inputs[0].sample(frac=1, random_state=9))
    assert a == b
    pd.testing.assert_frame_equal(groups_a, groups_b)


def test_missing_query_fields_use_neutral_text(inputs):
    p = inputs[0][["record_id", "Metadata_broad_sample"]].copy()
    rendered = render_queries(p, "M0_IDENTITY_FREE_V2")
    assert set(rendered.rendered_text) == {"cellular perturbation"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("Metadata_gene", "SYNTH_GENE_A"),
        ("Metadata_Plate", "SYNTH_PLATE_A"),
        ("Metadata_Well", "A01"),
        ("Metadata_broad_sample", "SYNTH_TREAT_A"),
        ("Metadata_target_sequence", "ACGTACGT"),
    ],
)
def test_leaked_identifiers_fail_closed(inputs, field, value):
    p = inputs[0].copy()
    p[field] = value
    p.loc[0, "Metadata_pert_type"] = value
    result = render_queries(p, "M0_IDENTITY_FREE_V2")
    assert result.blocked_fields.ne("").sum() >= 1


def test_missing_identity_does_not_manufacture_collision():
    stats, _ = query_counts(
        pd.DataFrame({"treatment": ["", "", "T"], "rendered_text": ["same"] * 3})
    )
    assert stats["collision_groups"] == 0
    assert stats["missing_treatment_queries"] == 2


def test_pair_diagnostics_matches_hand_computed_cosine(inputs):
    joined = join_cohort(*inputs)
    joined["Cells_a"] = [1, 1, 0, 0]
    joined["Cells_b"] = [0, 0, 1, 1]
    result = pair_diagnostics(joined, ["Cells_a", "Cells_b"])
    assert result.pairs.sum() == 6
    assert np.allclose(result.loc[result.same_treatment, "mean_cosine"], 1)
    assert np.allclose(result.loc[~result.same_treatment, "mean_cosine"], 0)


def test_multitarget_overlap_is_not_phenocopy(inputs):
    joined = join_cohort(*inputs)
    joined.loc[joined.broad_sample.eq("SYNTH_TREAT_B"), "Perturbation"] = "crispr"
    joined.loc[joined.Perturbation.eq("crispr"), "Time"] = "144"
    annotation = pd.DataFrame(
        {
            "broad_sample": ["SYNTH_TREAT_A"],
            "target": ["OTHER"],
            "target_list": ["OTHER|SYNTH_GENE_B"],
        }
    )
    result = target_overlap(joined, annotation)
    assert result["shared_principal_genes"] == 0
    assert result["shared_expanded_genes"] == 1
    assert result["multitarget_compound_rows"] == 1
    assert result["compound_crispr_time_matched"] is False
    joined["Time"] = "24"
    assert target_overlap(joined, annotation)["compound_crispr_time_matched"] is True


def test_pubchem_precision_conflict_does_not_change_sample_identity(inputs):
    p, e, b, m, a = inputs
    p["Metadata_pubchem_cid"] = ["9.8839e+06", "9883933.0", "5", "5"]
    a["pubchem_cid"] = ["9883933", "5"]
    joined = join_cohort(p, e, b, m, a)
    assert joined.resolved.all()
    assert joined.annotation_conflict.sum() == 1
    assert joined.loc[0, "annotation_conflict_fields"] == "pubchem_cid"


def test_permitted_gene_well_collision_is_reported_without_changing_contract(inputs):
    p = inputs[0].copy()
    p.loc[0, "Metadata_gene"] = "F10"
    p.loc[2, "Metadata_Well"] = "F10"
    rendered = render_queries(p, "M0_GENE_AWARE_V1")
    assert rendered.loc[0, "rendered_text"] == "cells with perturbation of F10"
    assert rendered.loc[0, "blocked_fields"] == "Metadata_Well"


def test_batch_scanner_matches_production_unicode_and_boundaries():
    from perturb_lm.audits.queries import scan_identifiers
    from perturb_lm.sklearn_api.queries import POLICIES, audit_text

    universe = pd.DataFrame({"Metadata_gene": ["ＡＢＣ", "IL-6", "A", "none"]})
    texts = ["abc", "IL-6", "IL-60", "a", "abcde", "IL-6-mediated"]
    scan = scan_identifiers(texts, "M0_IDENTITY_FREE_V2", universe)
    for text in texts:
        try:
            audit_text(text, POLICIES["M0_IDENTITY_FREE_V2"], universe)
        except ValueError:
            assert scan[text]
        else:
            assert not scan[text]


def test_audit_missing_optional_fields(inputs):
    p = inputs[0].drop(
        columns=["Metadata_gene", "Metadata_control_type", "Metadata_negcon_control_type"]
    )
    result, _ = audit_queries(p)
    assert result["M0_IDENTITY_FREE_V2"]["unique_strings"] == 1


def test_source_only_audit(tmp_path, inputs):
    from perturb_lm.audits.cohort import cohort_audit

    _, e, b, maps, annotation = inputs
    source = tmp_path / "source"
    source.mkdir()
    e.to_csv(source / "experiment-metadata.tsv", sep="\t", index=False)
    b.drop(columns="Batch").to_csv(source / "barcode_platemap.csv", index=False)
    # Replace synthetic map name with the source naming convention for this fixture.
    e.Plate_Map_Name = "JUMP-Target-1_compound_platemap"
    e.to_csv(source / "experiment-metadata.tsv", sep="\t", index=False)
    b.Plate_Map_Name = "JUMP-Target-1_compound_platemap"
    b.drop(columns="Batch").to_csv(source / "barcode_platemap.csv", index=False)
    for modality in ("compound", "crispr", "orf"):
        maps.drop(columns="Plate_Map_Name").to_csv(
            source / f"JUMP-Target-1_{modality}_platemap.txt", sep="\t", index=False
        )
        annotation.drop(columns="Perturbation").to_csv(
            source / f"JUMP-Target-1_{modality}_metadata.tsv", sep="\t", index=False
        )
    result = cohort_audit(None, source, tmp_path / "out")
    assert result["source_plate_count"] == 2
    assert result["local_status"].startswith("unavailable")
    assert not result["source_inventory_sanity_passed"]
    assert result["source_inventory_discrepancies"] == 0
