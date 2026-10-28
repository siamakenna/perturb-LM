"""Invented nomenclature and design metadata only; no real features (#30, #52)."""

from itertools import permutations
from math import isclose

import pytest

from perturb_lm.audits.cross_guide_design import (
    balanced_comparison_weights,
    coverage,
    relation,
)
from perturb_lm.audits.gene_identity import resolution_summary, resolve_symbols
from perturb_lm.audits.guide_support import training_plate_support
from perturb_lm.audits.support_inputs import manifest_path


def hgnc(identity="HGNC:900000001", symbol="SYNTH_A", **kwargs):
    return {"hgnc_id": identity, "symbol": symbol, "status": "Approved", **kwargs}


def test_approved_previous_and_alias_are_distinct():
    reference = [hgnc(prev_symbol="SYNTH_OLD", alias_symbol="SYNTH_ALIAS")]
    records = resolve_symbols(["SYNTH_A", "SYNTH_OLD", "SYNTH_ALIAS"], reference, [])
    by_label = {r["source_label"]: r for r in records}
    assert by_label["SYNTH_A"]["match_kind"] == "approved_symbol"
    assert by_label["SYNTH_OLD"]["hgnc_id"] == "HGNC:900000001"
    assert by_label["SYNTH_ALIAS"]["hgnc_id"] is None
    summary = resolution_summary(records)
    assert summary["stable_IDs_merging_multiple_source_strings"] == 1
    assert summary["source_strings_in_merged_groups"] == 2
    assert summary["independently_reviewed_biological_gene_identities"] == 0


def test_ambiguous_previous_alias_candidates_not_forced():
    refs = [
        hgnc(prev_symbol="SYNTH_OLD"),
        hgnc("HGNC:900000002", "SYNTH_B", alias_symbol="SYNTH_OLD"),
    ]
    row = resolve_symbols(["SYNTH_OLD"], refs, [])[0]
    assert row["match_kind"] == "ambiguous" and row["hgnc_id"] is None


def test_approved_symbol_precedence_preserves_secondary_conflict():
    refs = [hgnc(), hgnc("HGNC:900000002", "SYNTH_B", alias_symbol="SYNTH_A")]
    row = resolve_symbols(["SYNTH_A"], refs, [])[0]
    assert row["hgnc_id"] == "HGNC:900000001"
    assert row["secondary_candidate_conflict"]


def test_withdrawn_split_unmapped_and_case_are_preserved():
    withdrawn = [{"WITHDRAWN_SYMBOL": "SYNTH_GONE", "STATUS": "Merged/Split"}]
    rows = resolve_symbols(["SYNTH_GONE", "synth_a", "SYNTH_UNKNOWN"], [hgnc()], withdrawn)
    assert {r["match_kind"] for r in rows} == {"withdrawn", "unmapped"}
    assert next(r for r in rows if r["source_label"] == "SYNTH_GONE")["withdrawn_records"]
    assert all(r["hgnc_id"] is None for r in rows)


def test_nomenclature_order_invariance_and_duplicate_reference_failure():
    refs = [hgnc(), hgnc("HGNC:900000002", "SYNTH_B")]
    labels = ["SYNTH_B", "SYNTH_A"]
    assert resolve_symbols(labels, refs, []) == resolve_symbols(labels[::-1], refs[::-1], [])
    with pytest.raises(ValueError, match="duplicate"):
        resolve_symbols(labels, [refs[0], refs[0]], [])


def test_both_training_plates_not_merely_union_support():
    import pandas as pd

    queries = pd.DataFrame({"broad_sample": ["SYNTH_A", "SYNTH_B", "SYNTH_C"]})
    training = pd.DataFrame(
        {
            "broad_sample": ["SYNTH_A", "SYNTH_B", "SYNTH_A"],
            "Assay_Plate_Barcode": ["SYNTH_P1", "SYNTH_P1", "SYNTH_P2"],
        }
    )
    result = training_plate_support(queries, training, ["SYNTH_P1", "SYNTH_P2"])
    assert result["query_wells_seen_on_both_training_plates"] == 1
    assert result["query_wells_seen_on_either_training_plate"] == 2
    empty = training_plate_support(queries, training, ["SYNTH_P1", "SYNTH_EMPTY"])
    assert not empty["both_training_plates_contribute_usable_noncontrol_records"]
    assert empty["query_wells_seen_on_both_training_plates"] == 0


def guide(**kwargs):
    return {
        "reviewed": True,
        "gene_id": "SYNTH_GENE_A",
        "guide_id": "SYNTH_GUIDE_A",
        "sequence": "ACACAC",
        "plate": "SYNTH_P1",
        "well": "A01",
        "condition": "SYNTH_MATCHED",
        **kwargs,
    }


def partner(**kwargs):
    return guide(
        guide_id="SYNTH_GUIDE_B", sequence="TGTGTG", plate="SYNTH_P2", well="B02", **kwargs
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "same_gene_other_guide"),
        ({"gene_id": "SYNTH_GENE_B"}, "reference"),
        ({"reviewed": False}, "unlabeled"),
        ({"sequence": ""}, "unlabeled"),
        ({"gene_id": ""}, "unlabeled"),
        ({"condition": "SYNTH_OTHER"}, "excluded_condition"),
        ({"plate": "SYNTH_P1"}, "excluded_same_plate"),
        ({"sequence": "ACACAC"}, "excluded_same_guide_or_sequence"),
        ({"well": "A02"}, "excluded_position"),
        ({"well": "B01"}, "excluded_position"),
    ],
)
def test_relations(changes, expected):
    candidate = partner()
    candidate.update(changes)
    assert relation(guide(), candidate) == expected


def test_canonical_guide_contradictions_fail_even_outside_spatial_pool():
    other = guide(plate="SYNTH_P2", sequence="TGTGTG")
    with pytest.raises(ValueError, match="contradicts"):
        relation(guide(), other)
    with pytest.raises(ValueError, match="contradicts"):
        relation(guide(), guide(plate="SYNTH_P2", gene_id="SYNTH_GENE_B"))


def test_same_reagent_cannot_be_promoted_to_independent_guide():
    a = guide(reagent_id="SYNTH_REAGENT_A")
    b = partner(reagent_id="SYNTH_REAGENT_A")
    with pytest.raises(ValueError, match="contradicts"):
        relation(a, b)
    b["sequence"] = a["sequence"]
    assert relation(a, b) == "excluded_same_guide_or_sequence"


def test_spatial_sensitivity_and_full_gallery_coverage():
    same_row = partner()
    same_row["well"] = "A02"
    assert relation(guide(), same_row, "different_coordinate") == "same_gene_other_guide"
    assert relation(guide(well="a1"), same_row) == "excluded_position"
    anchors = [guide(), guide(gene_id="SYNTH_UNSUPPORTED", guide_id="SYNTH_C", well="C03")]
    reference = partner(gene_id="SYNTH_GENE_B")
    reference.update(guide_id="SYNTH_REFERENCE", well="D04")
    gallery = [partner(), reference]
    result = coverage(anchors, gallery)
    assert result["total_anchors"] == result["base_gallery_records"] == 2
    assert result["supported_anchors"] == result["no_positive_anchors"] == 1
    assert result["contrast_eligible_anchors"] == 1
    assert coverage(anchors[::-1], gallery[::-1]) == result
    assert coverage(anchors, [partner()])["no_reference_anchors"] == 1


def test_empty_population_and_duplicate_wells_are_explicit():
    result = coverage([guide()], [])
    assert result["no_positive_anchors"] == result["no_reference_anchors"] == 1
    assert coverage([], [partner()])["no_positive_anchors"] == 0
    with pytest.raises(ValueError, match="Duplicate"):
        coverage([guide(), guide(well="a1")], [])
    with pytest.raises(ValueError, match="mask"):
        coverage([], [], "SYNTH_BAD")


def test_invalid_masks_and_physical_identity_fail_closed():
    with pytest.raises(ValueError, match="mask"):
        relation(guide(), partner(), "SYNTH_BAD")
    with pytest.raises(ValueError, match="well"):
        relation(guide(well="Z99"), partner())
    with pytest.raises(ValueError, match="Physical"):
        relation(guide(plate=""), partner())


PLATES = ("SYNTH_P1", "SYNTH_P2", "SYNTH_P3", "SYNTH_P4")


def observations(gene="SYNTH_GENE_A", guides=("SYNTH_A", "SYNTH_B")):
    wells = {"SYNTH_A": "A01", "SYNTH_B": "B02", "SYNTH_C": "C03", "SYNTH_D": "D04"}
    return [
        (gene, guide, partner, p, q, wells[guide])
        for p, q in permutations(PLATES, 2)
        for guide, partner in (guides, guides[::-1])
    ]


def test_balanced_weights_repeat_orientations_within_genes():
    rows = observations() + observations("SYNTH_GENE_B", ("SYNTH_C", "SYNTH_D"))
    # Unequal well counts in one metadata cell must not increase its gene's weight.
    rows.append((*rows[0][:-1], "E05"))
    result = balanced_comparison_weights(rows, PLATES)
    assert result["eligible_gene_groups"] == 2
    assert result["complete_guide_pairs"] == 2
    assert isclose(sum(w for _, w in result["weights"]), 1)
    for gene in ("SYNTH_GENE_A", "SYNTH_GENE_B"):
        assert isclose(sum(w for row, w in result["weights"] if row[0] == gene), 0.5)
    assert result == balanced_comparison_weights(rows[::-1], PLATES[::-1])
    assert result["independent_experiments"] is None


def test_incomplete_or_duplicate_comparisons_do_not_create_replication():
    rows = observations()
    result = balanced_comparison_weights(rows[:-1], PLATES)
    assert result["eligible_gene_groups"] == 0 and result["weights"] == []
    with pytest.raises(ValueError, match="Duplicate"):
        balanced_comparison_weights(rows + [rows[0]], PLATES)


def test_multiple_guide_pairs_and_invalid_plates():
    rows = observations() + observations(guides=("SYNTH_A", "SYNTH_C"))
    result = balanced_comparison_weights(rows, PLATES)
    assert result["complete_guide_pairs"] == 2
    assert isclose(sum(w for _, w in result["weights"]), 1)
    with pytest.raises(ValueError, match="four"):
        balanced_comparison_weights(rows, PLATES[:3])


def test_contradictory_physical_anchor_fails_before_weighting():
    rows = observations()
    conflicting = ("SYNTH_OTHER_GENE", *rows[0][1:])
    with pytest.raises(ValueError, match="Physical"):
        balanced_comparison_weights(rows + [conflicting], PLATES)


def test_weighting_well_alias_duplicate_does_not_create_an_extra_observation():
    rows = observations()
    alias = (*rows[0][:-1], "a1")
    with pytest.raises(ValueError, match="Duplicate"):
        balanced_comparison_weights(rows + [alias], PLATES)


def test_weighting_well_alias_cannot_hide_a_physical_identity_conflict():
    rows = observations()
    conflicting = ("SYNTH_OTHER_GENE", *rows[0][1:-1], "a1")
    with pytest.raises(ValueError, match="Physical"):
        balanced_comparison_weights(rows + [conflicting], PLATES)


def test_weighting_well_aliases_and_reordering_preserve_canonical_weights():
    rows = observations() + observations("SYNTH_GENE_B", ("SYNTH_C", "SYNTH_D"))
    aliases = [(*row[:-1], row[-1][0].lower() + str(int(row[-1][1:]))) for row in rows]
    expected = balanced_comparison_weights(rows, PLATES)
    assert balanced_comparison_weights(aliases[::-1], PLATES[::-1]) == expected
    assert isclose(sum(weight for _, weight in expected["weights"]), 1)


def test_weighting_rejects_invalid_physical_wells():
    rows = observations()
    for well in ("A00", "A25", "Q01", "A001", "A01 ", 1):
        with pytest.raises(ValueError, match="physical well"):
            balanced_comparison_weights([(*rows[0][:-1], well), *rows[1:]], PLATES)


def test_manifest_containment_returns_checked_canonical_path(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "metadata.txt"
    target.write_text("SYNTHETIC_METADATA_ONLY")
    alias = root / "alias.txt"
    alias.symlink_to(target)
    assert manifest_path(root, "alias.txt") == target.resolve()
    assert manifest_path(root, "metadata.txt") == target.resolve()
    with pytest.raises(ValueError, match="missing"):
        manifest_path(root, "missing.txt")


def test_manifest_rejects_symlink_escape_and_sibling_prefix(tmp_path):
    root, sibling = tmp_path / "root", tmp_path / "root_extra"
    root.mkdir()
    sibling.mkdir()
    outside = sibling / "metadata.txt"
    outside.write_text("SYNTHETIC_OUTSIDE_METADATA")
    (root / "escape.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        manifest_path(root, "escape.txt")
    with pytest.raises(ValueError, match="relative"):
        manifest_path(root, "../root_extra/metadata.txt")
    with pytest.raises(ValueError, match="relative"):
        manifest_path(root, outside)


@pytest.mark.parametrize("tamper_receipt", [False, True])
def test_offline_cli_receipt_binding_and_private_ledger(tamper_receipt):
    import csv
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from test_phase5_guide_support import fixture

    from perturb_lm.audits.cohort import checksum

    root = Path(__file__).resolve().parents[1]
    (root / "outputs").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / "outputs") as directory:
        temporary = Path(directory)
        audit = temporary / "audit"
        (audit / "cohort").mkdir(parents=True)
        (audit / "source").mkdir()
        rows, annotations = fixture()
        mapping = audit / "cohort/local_mapping_PRIVATE.csv"
        rows.to_csv(mapping, index=False)
        ann = audit / "source/JUMP-Target-1_crispr_metadata.tsv"
        annotations.to_csv(ann, index=False, sep="\t")
        provenance = audit / "source/provenance.json"
        provenance.write_text(json.dumps({"files": [{"path": ann.name, "sha256": checksum(ann)}]}))
        census = temporary / "census.json"
        census.write_text(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "verification": {
                        "verified": True,
                        "input_manifest_sha256": {
                            "original_mapping": checksum(mapping),
                            "original_source_provenance": checksum(provenance),
                        },
                    },
                }
            )
        )
        reference = temporary / "approved.tsv"
        genes = sorted(set(rows.loc[rows.Metadata_pert_type.eq("trt"), "Metadata_gene"]))
        with reference.open("w") as stream:
            writer = csv.DictWriter(
                stream, delimiter="\t", fieldnames=["hgnc_id", "symbol", "status"]
            )
            writer.writeheader()
            writer.writerows(hgnc(f"HGNC:90000000{i}", gene) for i, gene in enumerate(genes))
        withdrawn = temporary / "withdrawn.tsv"
        withdrawn.write_text("HGNC_ID\tSTATUS\tWITHDRAWN_SYMBOL\n")
        manifest = temporary / "reference.json"
        manifest.write_text(
            json.dumps(
                {
                    "approved": {"sha256": checksum(reference)},
                    "withdrawn": {"sha256": checksum(withdrawn)},
                }
            )
        )
        out = temporary / "result"
        command = [
            sys.executable,
            str(root / "scripts/prepare_phase5_cross_guide_readiness.py"),
            "--audit-root",
            str(audit),
            "--census-summary",
            str(census),
            "--expected-summary-sha256",
            "SYNTH_BAD" if tamper_receipt else checksum(census),
            "--hgnc-approved",
            str(reference),
            "--hgnc-withdrawn",
            str(withdrawn),
            "--reference-manifest",
            str(manifest),
            "--out",
            str(out),
        ]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        result = subprocess.run(command, cwd=temporary, env=env, capture_output=True, text=True)
        if tamper_receipt:
            assert result.returncode != 0 and not out.exists()
            assert "Census receipt checksum mismatch" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
            ledger = json.loads((out / "identity-ledger_PRIVATE.json").read_text())
            summary = json.loads((out / "identity-summary.json").read_text())
            assert len(ledger) == summary["resolution"]["source_gene_strings"] == len(genes)
            assert all(not row["biological_identity_reviewed"] for row in ledger)
            assert summary["source_gene_to_assigned_HGNC_partition_is_one_to_one_complete"]
            assert not summary["profiles_read"] and not summary["census_rerun"]
            assert not any(gene in (out / "identity-summary.json").read_text() for gene in genes)
