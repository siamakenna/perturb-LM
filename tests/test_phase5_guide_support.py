"""Invented metadata only; no real sequences, biological labels or scores (#30,#52)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from perturb_lm.audits.cohort import BATCH, checksum, read_table
from perturb_lm.audits.guide_support import (
    IdentityError,
    sequence,
    support_census,
)
from perturb_lm.audits.rotations import PLATES, canonical_wells, plan_rotations, plate_roles
from perturb_lm.audits.support_inputs import compare_mapping, manifest_path, metadata_profiles

FIXTURE = Path(__file__).parent / "fixtures/phase5_1/rotation_mapping_synthetic.csv"


def fixture():
    rows = read_table(FIXTURE)
    sequences = {
        "SYNTH_TREAT_A": "ACGTACGT",
        "SYNTH_TREAT_B": "CGTACGTA",
        "SYNTH_TREAT_C": "GTACGTAC",
        "SYNTH_CONTROL": "",
    }
    rows["gene"] = rows.Metadata_gene
    rows["target_sequence"] = rows.broad_sample.map(sequences).fillna("")
    rows["Metadata_target_sequence"] = rows.target_sequence
    ann = rows[rows.broad_sample.ne("")].drop_duplicates("broad_sample")[
        ["broad_sample", "gene", "target_sequence", "Perturbation"]
    ]
    return rows, ann


def first(
    result, mask="different_coordinate", endpoint="B_different_reagent_sequence_same_source_gene"
):
    return result["assignments"][0]["spatial_masks"][mask][endpoint]


def test_reuses_exact_planner_roles_and_canonicalization():
    rows, ann = fixture()
    census = support_census(rows, ann)
    plan, _ = plan_rotations(
        rows, min_train_groups=3, min_evaluable_groups=2, upstream_normalization_scope="unknown"
    )
    assert len(census["assignments"]) == 12
    assert [
        (r["query_plate"], r["gallery_plate"], r["training_plates"]) for r in census["assignments"]
    ] == list(plate_roles())
    for a, b in zip(census["assignments"], plan["rotations"], strict=True):
        assert (
            a["spatial_masks"]["different_coordinate"]["A_exact_reagent"][
                "training_supported_seen_query_reagent"
            ]["wells"]
            == b["evaluable"]["profile_rows"]
        )
    assert canonical_wells(pd.Series(["a1", "p24"])).tolist() == ["A01", "P24"]
    assert census["minimum_thresholds"] is None and not census["execution_allowed"]


def test_different_sequence_same_gene_capacity_is_separate_from_exact_reagent():
    rows, ann = fixture()
    result = support_census(rows, ann)
    a = first(result, endpoint="A_exact_reagent")
    b = first(result)
    assert a["raw_gallery_supported_queries"]["wells"] == 3
    assert b["raw_gallery_supported_queries"]["wells"] == 3
    assert a["query_positive_well_pairs"] == 3
    assert b["query_positive_well_pairs"] == 4
    assert b["no_positive_query_wells"] == 1
    assert b["positive_well_count_histogram"] == {"0": 1, "1": 2, "2": 1}
    assert result["assignments"][0]["populations"]["gallery"]["wells"] == 4
    assert result["selected_noncontrol_population"]["reviewed_stable_genes"] == 0


def test_identical_sequence_other_ids_do_not_establish_cross_guide_support():
    rows, ann = fixture()
    rows.loc[
        rows.broad_sample.eq("SYNTH_TREAT_C"), ["target_sequence", "Metadata_target_sequence"]
    ] = "ACGTACGT"
    ann.loc[ann.broad_sample.eq("SYNTH_TREAT_C"), "target_sequence"] = "ACGTACGT"
    b = first(support_census(rows, ann))
    assert b["raw_gallery_supported_queries"]["wells"] == 0
    assert b["same_sequence_other_reagent_gene_pairs_rejected_for_B"] == 4


def test_stricter_mask_requires_both_row_and_column_different():
    rows, ann = fixture()
    rows.loc[rows.broad_sample.eq("SYNTH_TREAT_C"), "well_position"] = "C03"
    result = support_census(rows, ann)
    b = first(result, "different_row_and_column")
    assert b["raw_gallery_supported_queries"]["wells"] == 3
    assert (
        first(result, "different_row_and_column", "A_exact_reagent")[
            "raw_gallery_supported_queries"
        ]["wells"]
        == 0
    )
    assert sum(int(k) * v for k, v in b["candidate_well_count_histogram"].items()) == 8


def test_raw_support_survives_unseen_query_reagent_and_gallery_remains_full():
    rows, ann = fixture()
    rows = rows[
        ~(rows.Assay_Plate_Barcode.isin(PLATES[2:]) & rows.broad_sample.eq("SYNTH_TREAT_C"))
    ]
    b = first(support_census(rows, ann))
    assert b["raw_gallery_supported_queries"]["wells"] == 3
    assert b["training_supported_seen_query_reagent"]["wells"] == 2
    assert b["training_supported_seen_query_and_positive_reagents"]["wells"] == 0
    assert b["positive_but_query_reagent_unseen_wells"] == 1


@pytest.mark.parametrize(
    "field", ["Metadata_gene", "gene", "Metadata_target_sequence", "target_sequence"]
)
def test_conflicts_fail_even_with_resolved_true(field):
    rows, ann = fixture()
    rows.loc[0, field] = "SYNTH_DISAGREEMENT"
    with pytest.raises(IdentityError) as error:
        support_census(rows, ann)
    assert error.value.counts["conflict_rows_previously_resolved_true"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("Time", "24"),
        ("Antibiotics", "Puromycin"),
        ("Density", "50"),
        ("Times_imaged", "2"),
        ("Anomaly", "none"),
        ("Cell_line", "parental"),
    ],
)
def test_condition_contradictions_stop_both_endpoints(field, value):
    rows, ann = fixture()
    rows.loc[0, field] = value
    with pytest.raises(ValueError, match="conditions"):
        support_census(rows, ann)


def test_duplicate_physical_well_stops_even_with_unique_record_id():
    rows, ann = fixture()
    extra = rows.iloc[[0]].assign(record_id="SYNTH_DUPLICATE_PHYSICAL")
    with pytest.raises(ValueError, match="Duplicate physical"):
        support_census(pd.concat([rows, extra]), ann)


@pytest.mark.parametrize("value", ["", "ACGN", "A-CG", "123"])
def test_missing_invalid_sequence_only_excludes_B_not_gallery_or_exact(value):
    rows, ann = fixture()
    rows.loc[
        rows.broad_sample.eq("SYNTH_TREAT_C"), ["target_sequence", "Metadata_target_sequence"]
    ] = value
    ann.loc[ann.broad_sample.eq("SYNTH_TREAT_C"), "target_sequence"] = value
    result = support_census(rows, ann)
    assert first(result)["raw_gallery_supported_queries"]["wells"] == 0
    assert first(result, endpoint="A_exact_reagent")["raw_gallery_supported_queries"]["wells"] == 3
    assert result["assignments"][0]["populations"]["gallery"]["wells"] == 4


def test_ambiguous_source_sequence_gene_association_excluded_without_alias_guessing():
    rows, ann = fixture()
    extra = ann.iloc[[0]].assign(broad_sample="SYNTH_OTHER_REAGENT", gene="SYNTH_OTHER_GENE")
    result = support_census(rows, pd.concat([ann, extra]))
    assert result["identity_checks"]["source_sequences_with_multiple_gene_strings"] == 1
    assert first(result)["raw_gallery_supported_queries"]["wells"] == 0


def test_source_duplicate_and_multi_gene_annotation_not_silently_resolved():
    rows, ann = fixture()
    with pytest.raises(IdentityError):
        support_census(rows, pd.concat([ann, ann.iloc[:1]]))
    rows.loc[rows.gene.eq("SYNTH_GENE_X"), ["gene", "Metadata_gene"]] = "SYNTH_GENE_X|SYNTH_GENE_Y"
    ann.loc[ann.gene.eq("SYNTH_GENE_X"), "gene"] = "SYNTH_GENE_X|SYNTH_GENE_Y"
    assert first(support_census(rows, ann))["raw_gallery_supported_queries"]["wells"] == 0


def test_deterministic_and_aggregate_without_private_identifiers():
    rows, ann = fixture()
    a = support_census(rows, ann)
    b = support_census(rows.sample(frac=1, random_state=7), ann.sample(frac=1, random_state=9))
    assert a == b
    text = json.dumps(a)
    for private in ["SYNTH_TREAT", "SYNTH_GENE", "ACGTACGT", "SYNTH_RECORD"]:
        assert private not in text


def test_complete_mapping_comparison_does_not_accept_historical_count_substitution():
    rows, _ = fixture()
    assert compare_mapping(rows, rows)["matches"]
    assert not compare_mapping(rows.iloc[:-1], rows)["matches"]
    changed = rows.copy()
    changed.loc[0, "Metadata_target_sequence"] = "TTTT"
    assert not compare_mapping(changed, rows)["matches"]
    assert not compare_mapping(pd.concat([rows, rows.iloc[:1]]), rows)["matches"]


def test_metadata_reader_does_not_parse_features_and_verifies_hash_and_header(tmp_path):
    relative = f"profiles/{BATCH}/synthetic_normalized_feature_select_negcon_batch.csv.gz"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    with gzip.open(target, "wt") as f:
        f.write(
            "Metadata_Plate,Metadata_Well,Metadata_gene,Cells_Invented\nSYNTH_PLATE,A01,SYNTH_GENE,not-a-number\n"
        )
    import hashlib

    manifest = [
        {
            "relative_path": relative,
            "sha256": checksum(target),
            "rows": 1,
            "plates_observed_in_rows": ["SYNTH_PLATE"],
            "feature_count": 1,
            "feature_schema_sha256": hashlib.sha256(b"Cells_Invented").hexdigest(),
        }
    ]
    rows, checks = metadata_profiles(tmp_path, manifest)
    assert "Cells_Invented" not in rows and checks[0]["hash_matches"]
    manifest[0]["sha256"] = "0" * 64
    assert not metadata_profiles(tmp_path, manifest)[1][0]["hash_matches"]
    with pytest.raises(ValueError):
        manifest_path(tmp_path, "../outside")
    with pytest.raises(ValueError):
        manifest_path(tmp_path, "/absolute")


def test_sequence_canonicalization_does_not_invent_length_threshold():
    assert sequence(" acgt ") == "ACGT"
    assert sequence("ACGT" * 5) == "ACGT" * 5
    assert sequence("ACGN") == ""


@pytest.fixture
def original_input_fixture(tmp_path):
    """Twelve tiny invented profile files and eleven invented metadata source files."""
    import hashlib

    from perturb_lm.audits.cohort import CONDITIONS, join_cohort, replication, source_tables

    audit, data = tmp_path / "audit", tmp_path / "data"
    source, cohort = audit / "source", audit / "cohort"
    source.mkdir(parents=True)
    cohort.mkdir()
    base = read_table(FIXTURE).iloc[0]
    plates = list(PLATES) + [f"SYNTH_PLATE_{i}" for i in range(8)]
    experiments = pd.DataFrame(
        [
            {
                "Batch": BATCH,
                "Assay_Plate_Barcode": plate,
                "Plate_Map_Name": "JUMP-Target-1_crispr_platemap",
                **{c: base[c] for c in CONDITIONS},
            }
            for plate in plates
        ]
    )
    experiments.to_csv(source / "experiment-metadata.tsv", sep="\t", index=False)
    experiments[["Assay_Plate_Barcode", "Plate_Map_Name"]].to_csv(
        source / "barcode_platemap.csv", index=False
    )
    for modality in ("compound", "crispr", "orf"):
        pd.DataFrame([{"well_position": "A01", "broad_sample": "SYNTH_A"}]).to_csv(
            source / f"JUMP-Target-1_{modality}_platemap.txt", sep="\t", index=False
        )
        pd.DataFrame(
            [
                {
                    "broad_sample": "SYNTH_A",
                    "gene": "SYNTH_GENE",
                    "target_sequence": "ACGTACGT",
                    "pert_type": "trt",
                }
            ]
        ).to_csv(source / f"JUMP-Target-1_{modality}_metadata.tsv", sep="\t", index=False)
    for name in (
        "README.md",
        "0.create-experiment-metadata.ipynb",
        "JUMP-Target-1_compound_metadata_targets.tsv",
    ):
        (source / name).write_text("SYNTHETIC_FIXTURE\n")
    entries = []
    for plate in sorted(plates):
        relative = f"profiles/{BATCH}/{plate}/{plate}_normalized_feature_select_negcon_batch.csv.gz"
        path = data / relative
        path.parent.mkdir(parents=True)
        with gzip.open(path, "wt") as f:
            f.write(
                "Metadata_Plate,Metadata_Well,Metadata_broad_sample,Metadata_gene,"
                "Metadata_target_sequence,Metadata_pert_type,Cells_Invented\n"
            )
            f.write(f"{plate},A01,SYNTH_A,SYNTH_GENE,ACGTACGT,trt,never-parsed\n")
        entries.append(
            {
                "relative_path": relative,
                "sha256": checksum(path),
                "rows": 1,
                "plates_observed_in_rows": [plate],
                "feature_count": 1,
                "feature_schema_sha256": hashlib.sha256(b"Cells_Invented").hexdigest(),
            }
        )
    (cohort / "profile_manifest.json").write_text(json.dumps(entries))
    profiles, _ = metadata_profiles(data, entries)
    joined = join_cohort(profiles, *source_tables(source))
    joined.to_csv(cohort / "local_mapping_PRIVATE.csv", index=False)
    original = {
        "source_revision": "SYNTHETIC_REVISION",
        "source_plate_count": 12,
        "source_modalities": {"crispr": 12},
        "source_files": {p.name: checksum(p) for p in source.iterdir()},
        "local_files": 12,
        "local_rows": 12,
        "labeled_rows": 12,
        "missing_treatment_rows": 0,
        "local_plate_count": 12,
        "resolved_rows": 12,
        "unresolved_rows": 0,
        "annotation_conflict_rows": 0,
        "local_modalities": {"crispr": 12},
        "local_cell_types": {"U2OS": 12},
        "replication": replication(joined)[0],
    }
    (cohort / "cohort_summary.json").write_text(json.dumps(original))
    (source / "provenance.json").write_text(
        json.dumps(
            {
                "revision": "SYNTHETIC_REVISION",
                "files": [
                    {"path": p.name, "sha256": checksum(p), "bytes": p.stat().st_size}
                    for p in sorted(source.iterdir())
                ],
            }
        )
    )
    return audit, data


def test_complete_input_verification_uses_all_original_bytes_and_rows(original_input_fixture):
    from perturb_lm.audits.support_inputs import verify_inputs

    audit, data = original_input_fixture
    _, _, evidence, _ = verify_inputs(audit, data)
    assert evidence["verified"] and len(evidence["source_files"]) == 11
    assert len(evidence["profile_files"]) == 12
    assert evidence["complete_original_mapping_reproduction"]["matches"]


@pytest.mark.parametrize("damage", ["source_hash", "profile_hash", "missing_mapping_row"])
def test_original_input_discrepancies_block_census(original_input_fixture, damage):
    from perturb_lm.audits.support_inputs import VerificationError, verify_inputs

    audit, data = original_input_fixture
    if damage == "source_hash":
        (audit / "source/README.md").write_text("SYNTH_CHANGED\n")
    elif damage == "profile_hash":
        path = next(data.rglob("*.csv.gz"))
        with path.open("ab") as f:
            f.write(b"\x00")  # Valid gzip padding, but not the preserved bytes.
    else:
        mapping = audit / "cohort/local_mapping_PRIVATE.csv"
        read_table(mapping).iloc[:-1].to_csv(mapping, index=False)
    with pytest.raises(VerificationError):
        verify_inputs(audit, data)


def test_additional_recorded_imaging_count_is_preserved_and_mixture_stops():
    rows, ann = fixture()
    rows["Number_of_images"] = "SYNTH_SAME_COUNT"
    assert support_census(rows, ann)["recorded_Number_of_images"] == "SYNTH_SAME_COUNT"
    rows.loc[0, "Number_of_images"] = "SYNTH_OTHER_COUNT"
    with pytest.raises(ValueError, match="imaging conditions"):
        support_census(rows, ann)


def test_review_sequence_case_aliases_are_not_independent_guides():
    rows, ann = fixture()
    for reagent, value in (("SYNTH_TREAT_A", "acgtacgt"), ("SYNTH_TREAT_C", "ACGTACGT")):
        rows.loc[rows.broad_sample.eq(reagent), ["target_sequence", "Metadata_target_sequence"]] = (
            value
        )
        ann.loc[ann.broad_sample.eq(reagent), "target_sequence"] = value
    result = support_census(rows, ann)
    assert first(result)["raw_gallery_supported_queries"]["wells"] == 0
    assert result["identity_checks"]["source_sequences_shared_by_multiple_reagent_ids"] == 1
    assert not result["execution_allowed"]


def test_review_gene_strings_are_not_automatically_stable_gene_aliases():
    rows, ann = fixture()
    rows.loc[rows.broad_sample.eq("SYNTH_TREAT_C"), ["gene", "Metadata_gene"]] = "SYNTH_ALIAS_X"
    ann.loc[ann.broad_sample.eq("SYNTH_TREAT_C"), "gene"] = "SYNTH_ALIAS_X"
    result = support_census(rows, ann)
    assert first(result)["raw_gallery_supported_queries"]["wells"] == 0
    assert result["selected_noncontrol_population"]["source_gene_strings"] == 3
    assert result["selected_noncontrol_population"]["reviewed_stable_genes"] == 0


def test_review_unseen_reagent_id_does_not_mean_unseen_guide_sequence():
    rows, ann = fixture()
    training_alias = rows.Assay_Plate_Barcode.isin(PLATES[2:]) & rows.broad_sample.eq(
        "SYNTH_TREAT_A"
    )
    rows.loc[training_alias, "broad_sample"] = "SYNTH_ALIAS_REAGENT_A"
    alias = ann[ann.broad_sample.eq("SYNTH_TREAT_A")].assign(broad_sample="SYNTH_ALIAS_REAGENT_A")
    result = support_census(rows, pd.concat([ann, alias], ignore_index=True))
    endpoint = first(result)
    assert endpoint["raw_gallery_supported_queries"]["wells"] == 3
    assert endpoint["training_supported_seen_query_reagent"]["wells"] == 1
    assert endpoint["query_reagent_not_seen_in_training_wells"] == 2
    # The query ID is absent in training, but its exact sequence is exposed through an alias ID.
    assert set(rows.loc[training_alias, "target_sequence"]) == {"ACGTACGT"}
    assert result["identity_checks"]["source_sequences_shared_by_multiple_reagent_ids"] == 1


def test_review_both_endpoints_share_full_candidate_masks_and_zero_support_denominators():
    result = support_census(*fixture())
    for assignment in result["assignments"]:
        for endpoints in assignment["spatial_masks"].values():
            a, b = (
                endpoints["A_exact_reagent"],
                endpoints["B_different_reagent_sequence_same_source_gene"],
            )
            assert a["candidate_well_count_histogram"] == b["candidate_well_count_histogram"]
            for endpoint in (a, b):
                assert endpoint["total_query_wells"] == 4
                assert (
                    endpoint["no_positive_query_wells"]
                    + endpoint["raw_gallery_supported_queries"]["wells"]
                    == 4
                )
            assert assignment["populations"]["gallery"]["wells"] == 4


def test_review_disjoint_support_is_an_observation_not_a_definition():
    rows, annotations = fixture()
    summary = support_census(rows, annotations)
    # In this invented example all three supported queries occur in both endpoints.
    query = rows[rows.Assay_Plate_Barcode.eq(PLATES[0]) & rows.Metadata_pert_type.eq("trt")]
    gallery = rows[rows.Assay_Plate_Barcode.eq(PLATES[1]) & rows.Metadata_pert_type.eq("trt")]
    a, b = set(), set()
    for record in query.itertuples():
        candidates = gallery[gallery.well_position.ne(record.well_position)]
        if candidates.broad_sample.eq(record.broad_sample).any():
            a.add(record.record_id)
        if (
            candidates.broad_sample.ne(record.broad_sample)
            & candidates.Metadata_gene.eq(record.Metadata_gene)
            & candidates.target_sequence.ne(record.target_sequence)
        ).any():
            b.add(record.record_id)
    assert len(a & b) == 3
    assert first(summary, endpoint="A_exact_reagent")["raw_gallery_supported_queries"]["wells"] == 3
    assert first(summary)["raw_gallery_supported_queries"]["wells"] == 3
