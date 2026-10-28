"""Synthetic unit tests only; no real profile data or empirical score claims."""

import json
import unittest

import numpy as np
import pandas as pd

from crossguide import MASKS, _position_similarities, analyze_crossguide
from perturb_lm.audits.cross_guide_design import balanced_comparison_weights, relation


def fixture():
    rows, vectors = [], []
    treatments = [
        ("A01", "GENE_A", "a1", "AAAA", [1.0, 0.0]),
        ("B02", "GENE_A", "a2", "AAAC", [1.0, 0.0]),
        ("C03", "GENE_B", "b1", "CCCC", [0.0, 1.0]),
        ("D04", "GENE_B", "b2", "CCCA", [0.0, 1.0]),
    ]
    for plate in ("p1", "p2", "p3", "p4"):
        for well, gene, reagent, sequence, vector in treatments:
            rows.append(dict(row_id=f"{plate}-{well}", plate=plate, well=well,
                             gene=gene, reagent=reagent, sequence=sequence,
                             condition="recorded stratum", treatment=True, control=False,
                             pert_type="trt", control_type="", negcon_control_type=""))
            vectors.append(vector)
        rows.append(dict(row_id=f"{plate}-P24", plate=plate, well="P24", gene="",
                         reagent="control", sequence="", condition="recorded stratum",
                         treatment=False, control=True, pert_type="control",
                         control_type="negcon", negcon_control_type="recorded control"))
        vectors.append([0.5, 0.5])
    return pd.DataFrame(rows), np.array(vectors)


def append_treatments(metadata, features, spec):
    extra, values = [], []
    for plate in ("p1", "p2", "p3", "p4"):
        for well, gene, reagent, sequence, vector in spec:
            extra.append(dict(row_id=f"{plate}-{well}", plate=plate, well=well,
                              gene=gene, reagent=reagent, sequence=sequence,
                              condition="recorded stratum", treatment=True, control=False,
                              pert_type="trt", control_type="", negcon_control_type=""))
            values.append(vector)
    return pd.concat([metadata, pd.DataFrame(extra)], ignore_index=True), np.vstack([features, values])


class CrossGuideTests(unittest.TestCase):
    def test_known_same_gene_versus_orthogonal_reference_and_all_cells(self):
        metadata, features = fixture()
        result = analyze_crossguide(metadata, features)
        json.dumps(result["summary"], allow_nan=False)
        self.assertFalse(result["summary"]["guide_reviewed"])
        self.assertFalse(result["summary"]["biology_reviewed"])
        for mask in MASKS:
            summary = result["summary"]["masks"][mask]
            self.assertAlmostEqual(summary["contrast"], 1.0)
            self.assertEqual(summary["initial_anchor_wells"], 16)
            self.assertEqual(summary["eligible_gene_groups"], 2)
            self.assertEqual(summary["complete_guide_pairs"], 2)
            self.assertEqual(len(summary["unordered_plate_pairs"]), 6)
            self.assertEqual(len(summary["ordered_plate_directions"]), 12)
            self.assertEqual(summary["base_gallery_record_comparisons"], 16 * 3 * 4)
            self.assertTrue(all(abs(x["contrast"] - 1) < 1e-12 for x in summary["unordered_plate_pairs"]))
        obs = result["private_observations"]
        for mask in MASKS:
            part = obs[obs["mask"].eq(mask)]
            self.assertEqual(len(part), 48)
            self.assertAlmostEqual(part.weight.sum(), 1.0)
            self.assertTrue(np.allclose(part.groupby("gene").weight.sum(), 0.5))
            self.assertTrue(np.allclose(part.groupby(["anchor_plate", "gallery_plate"]).weight.sum(), 1 / 12))
        self.assertEqual(result["summary"]["initial_noncontrol_anchors_per_plate"], dict.fromkeys(("p1", "p2", "p3", "p4"), 4))

    def test_zero_nonfinite_vectors_keep_denominators_and_unavailable_is_none(self):
        metadata, features = fixture()
        features[metadata.row_id.eq("p1-A01")] = 0
        features[metadata.row_id.eq("p1-C03")] = np.nan
        result = analyze_crossguide(metadata, features)
        self.assertEqual(result["summary"]["initial_noncontrol_anchors"], 16)
        self.assertEqual(result["summary"]["vector_status_noncontrol_rows"], {"nonfinite": 1, "valid": 14, "zero_norm": 1})
        self.assertEqual(len(result["private_anchors"]), 16 * 3 * 2)
        for mask in MASKS:
            self.assertIsNone(result["summary"]["masks"][mask]["contrast"])
            self.assertIsNone(result["summary"]["masks"][mask]["position_contrast"])
            self.assertEqual(result["summary"]["masks"][mask]["eligible_gene_groups"], 0)
        self.assertTrue(result["private_genes"].contrast.isna().all())
        json.dumps(result["summary"], allow_nan=False)

    def test_spatial_mask_excludes_same_row_or_same_column_not_only_both(self):
        metadata, features = fixture()
        # Guide a2 shares a row with a1, while b2 shares a column with b1.
        metadata.loc[metadata.reagent.eq("a2"), "well"] = "A02"
        metadata.loc[metadata.reagent.eq("b2"), "well"] = "D03"
        result = analyze_crossguide(metadata, features)
        primary = result["summary"]["masks"][MASKS[0]]
        secondary = result["summary"]["masks"][MASKS[1]]
        self.assertEqual(primary["eligible_gene_groups"], 0)
        self.assertEqual(secondary["eligible_gene_groups"], 2)
        self.assertIsNone(primary["contrast"])
        self.assertAlmostEqual(secondary["contrast"], 1.0)
        self.assertTrue(result["summary"]["paired_mask_difference"]["gene_cohort_composition_changed"])
        self.assertIsNone(result["summary"]["paired_mask_difference"]["contrast_difference"])

    def test_exact_sequence_alias_and_reverse_complement_are_excluded(self):
        metadata, features = fixture()
        metadata, features = append_treatments(metadata, features, [
            ("E05", "GENE_A", "a1_alias", "AAAA", [1, 0]),
            ("F06", "GENE_A", "a1_reverse", "TTTT", [1, 0]),
        ])
        result = analyze_crossguide(metadata, features)
        primary = result["private_anchors"]
        row = primary[primary["mask"].eq(MASKS[0]) & primary.row_id.eq("p1-A01") & primary.gallery_plate.eq("p2")].iloc[0]
        self.assertEqual(row.excluded_identical_DNA_string, 1)
        self.assertEqual(row.excluded_reverse_complement_DNA_string, 1)
        self.assertEqual(row.metadata_positive_wells, 1)
        self.assertEqual(row.base_gallery_records, 6)
        self.assertEqual(result["summary"]["noncontrol_sequence_groups_with_reagent_aliases"], 1)
        self.assertIn("not asserted", result["summary"]["reverse_complement_policy"])

    def test_unknown_and_well_like_source_genes_remain_unlabeled_in_full_gallery(self):
        metadata, features = fixture()
        metadata, features = append_treatments(metadata, features, [
            ("E05", "F10", "ambiguous_gene", "ACAC", [1, 0]),
            ("F06", "", "missing_gene", "CACA", [1, 0]),
            ("G07", "GENE_C", "missing_seq", "", [1, 0]),
        ])
        result = analyze_crossguide(metadata, features)
        self.assertEqual(result["summary"]["initial_noncontrol_anchors"], 28)
        for mask in MASKS:
            table = result["private_genes"][result["private_genes"]["mask"].eq(mask)]
            self.assertEqual(set(table.gene), {"GENE_A", "GENE_B", "F10", "", "GENE_C"})
            self.assertFalse(table.loc[table.gene.isin(["F10", "", "GENE_C"]), "complete_pair_eligible"].any())
        f10 = result["private_genes"][result["private_genes"].gene.eq("F10")]
        self.assertTrue(f10.source_gene_status.eq("unresolved_well_like_source_gene_identifier_ambiguity").all())
        row = result["private_anchors"].query("mask == @MASKS[0] and row_id == 'p1-A01' and gallery_plate == 'p2'").iloc[0]
        self.assertEqual(row.base_gallery_records, 7)
        self.assertEqual(row.unlabeled, 3)

    def test_reagent_identity_conflicts_and_duplicate_physical_wells_fail(self):
        for field, value in (("gene", "CONFLICT"), ("sequence", "AGAG")):
            metadata, features = fixture()
            metadata.loc[metadata.row_id.eq("p1-A01"), field] = value
            with self.assertRaisesRegex(ValueError, "reagent identity contradicts"):
                analyze_crossguide(metadata, features)
        metadata, features = fixture()
        metadata.loc[1, "well"] = "a1"
        with self.assertRaisesRegex(ValueError, "Duplicate physical"):
            analyze_crossguide(metadata, features)

    def test_unreviewed_recorded_strings_are_provisional_not_validated(self):
        metadata, features = fixture()
        metadata["reviewed"] = False
        result = analyze_crossguide(metadata, features)
        self.assertEqual(result["summary"]["status"], "EXPLORATORY_PROVISIONAL_UNREVIEWED")
        self.assertAlmostEqual(result["summary"]["masks"][MASKS[0]]["contrast"], 1.0)
        metadata["reviewed"] = True
        self.assertEqual(result["summary"], analyze_crossguide(metadata, features)["summary"])
        # The existing reviewed gate is preserved independently.
        a = dict(plate="p1", well="A01", condition="c", gene_id="A", guide_id="a1", sequence="AAAA", reviewed=False)
        b = dict(plate="p2", well="B02", condition="c", gene_id="A", guide_id="a2", sequence="AAAC", reviewed=False)
        self.assertEqual(relation(a, b), "unlabeled")

    def test_row_shuffle_and_repeated_well_aliases_do_not_change_equal_weight_effect(self):
        metadata, features = fixture()
        baseline = analyze_crossguide(metadata, features)
        order = np.random.default_rng(27).permutation(len(metadata))
        shuffled = analyze_crossguide(metadata.iloc[order], features[order])
        self.assertEqual(baseline["summary"], shuffled["summary"])
        # Extra physical wells of an existing sequence guide must average within
        # guide, rather than granting extra guide/gene weight.
        metadata, features = append_treatments(metadata, features, [
            ("E05", "GENE_A", "a1_alias", "AAAA", [1, 0]),
            ("F06", "GENE_A", "a1_alias", "AAAA", [1, 0]),
        ])
        repeated = analyze_crossguide(metadata, features)
        for mask in MASKS:
            self.assertAlmostEqual(repeated["summary"]["masks"][mask]["contrast"], baseline["summary"]["masks"][mask]["contrast"])
            weighted = repeated["private_observations"]
            weighted = weighted[weighted["mask"].eq(mask) & weighted.complete_pair_eligible]
            self.assertTrue(np.allclose(weighted.groupby("gene").weight.sum(), 0.5))

    def test_canonical_weights_match_hand_unequal_well_count_balance(self):
        plates = ["p1", "p2", "p3", "p4"]
        records = []
        from itertools import permutations
        for gene, guide_a, guide_b in (("A", "a1", "a2"), ("B", "b1", "b2")):
            for p, q in permutations(plates, 2):
                records.extend([(gene, guide_a, guide_b, p, q, "A01" if gene == "A" else "C03"),
                                (gene, guide_b, guide_a, p, q, "B02" if gene == "A" else "D04")])
                if gene == "A":
                    records.append((gene, guide_a, guide_b, p, q, "E05"))
        weights = dict(balanced_comparison_weights(records, plates)["weights"])
        # Hand cell denominator: 2 genes * 1 pair * 6 plate pairs *
        # 2 plate directions * 2 guide orientations * wells in this cell.
        self.assertAlmostEqual(weights[("A", "a1", "a2", "p1", "p2", "A01")], 1 / 96)
        self.assertAlmostEqual(weights[("A", "a2", "a1", "p1", "p2", "B02")], 1 / 48)
        self.assertAlmostEqual(sum(weights.values()), 1)
        # A a1 means (0 + 2)/2=1; A a2=3 => A effect 2;
        # B orientations both 10 => B effect 10; equal-gene mean=6.
        effect = sum(w * (0 if r[1] == "a1" and r[-1] == "A01" else 2 if r[1] == "a1" else 3 if r[0] == "A" else 10)
                     for r, w in weights.items())
        self.assertAlmostEqual(effect, 6)

    def test_reference_is_equal_wells_then_sequence_guides_then_other_genes(self):
        metadata, features = fixture()
        metadata, features = append_treatments(metadata, features, [
            ("E05", "GENE_B", "b3", "CACG", [1, 0]),
            ("F06", "GENE_C", "c1", "ACCG", [-1, 0]),
            ("G07", "GENE_B", "b3_alias", "CACG", [1, 0]),
        ])
        result = analyze_crossguide(metadata, features)
        obs = result["private_observations"]
        obs = obs[obs["mask"].eq(MASKS[0]) & obs.row_id.eq("p1-A01") & obs.gallery_plate.eq("p2")].iloc[0]
        # GENE_B's three sequence guides have similarities 0,0,1 => 1/3;
        # GENE_C has -1. Equal other genes: ((1/3)+(-1))/2=-1/3.
        self.assertAlmostEqual(obs.reference_mean_cosine, -1 / 3)
        self.assertAlmostEqual(obs.contrast, 4 / 3)
        self.assertEqual(obs.reference_wells, 5)
        self.assertEqual(obs.reference_guides, 4)
        self.assertEqual(obs.reference_genes, 2)

    def test_missing_positive_or_reference_unavailable_and_unsupported_gene_kept(self):
        metadata, features = fixture()
        keep = ~metadata.reagent.eq("b2")
        result = analyze_crossguide(metadata[keep], features[keep])
        for mask in MASKS:
            self.assertEqual(result["summary"]["masks"][mask]["eligible_gene_groups"], 1)
            genes = result["private_genes"]
            b = genes[genes["mask"].eq(mask) & genes.gene.eq("GENE_B")].iloc[0]
            self.assertTrue(pd.isna(b.contrast))
            self.assertEqual(b.initial_anchor_wells, 4)
        keep = metadata.gene.eq("GENE_A") | metadata.control
        result = analyze_crossguide(metadata[keep], features[keep])
        for mask in MASKS:
            self.assertIsNone(result["summary"]["masks"][mask]["contrast"])
            self.assertEqual(result["summary"]["masks"][mask]["no_metadata_reference_anchor_gallery_comparisons"], 24)

    def test_stable_normalization_handles_large_small_finite_vectors(self):
        metadata, features = fixture()
        features[metadata.gene.eq("GENE_A")] *= 1e300
        features[metadata.gene.eq("GENE_B")] *= 1e-300
        result = analyze_crossguide(metadata, features)
        self.assertEqual(result["summary"]["vector_status_noncontrol_rows"], {"valid": 16})
        self.assertAlmostEqual(result["summary"]["masks"][MASKS[0]]["contrast"], 1)

    def test_position_kernel_hand_coordinates_and_same_observation_weights(self):
        self.assertTrue(np.allclose(_position_similarities("A01", pd.Series(["A01", "P24", "P01", "A24"])), [1, 0, 0.5, 0.5]))
        metadata, features = fixture()
        result = analyze_crossguide(metadata, features)
        obs = result["private_observations"]
        row = obs[obs["mask"].eq(MASKS[0]) & obs.row_id.eq("p1-A01") & obs.gallery_plate.eq("p2")].iloc[0]
        factor = 1 / 15 + 1 / 23
        self.assertAlmostEqual(row.position_positive_mean, 1 - 0.5 * factor)
        self.assertAlmostEqual(row.position_reference_mean, 1 - 1.25 * factor)
        self.assertAlmostEqual(row.position_contrast, 0.75 * factor)
        self.assertAlmostEqual(result["summary"]["masks"][MASKS[0]]["position_contrast"], 0.5 * factor)
        for mask in MASKS:
            part = obs[obs["mask"].eq(mask)]
            self.assertAlmostEqual(np.dot(part.weight, part.position_contrast), result["summary"]["masks"][mask]["position_contrast"])

    def test_malformed_flags_and_misaligned_features_fail(self):
        metadata, features = fixture()
        metadata["control"] = metadata.control.astype(object)
        metadata.loc[0, "control"] = "unknown"
        with self.assertRaisesRegex(ValueError, "explicit"):
            analyze_crossguide(metadata, features)
        metadata, features = fixture()
        metadata.loc[0, "treatment"] = False
        with self.assertRaisesRegex(ValueError, "Treatment flag contradicts"):
            analyze_crossguide(metadata, features)
        with self.assertRaisesRegex(ValueError, "aligned row"):
            analyze_crossguide(metadata, features[:-1])

    def test_control_only_input_has_stable_empty_schemas_and_no_fabricated_effect(self):
        metadata, features = fixture()
        selected = metadata.control
        result = analyze_crossguide(metadata[selected], features[selected])
        self.assertEqual(result["summary"]["initial_noncontrol_anchors"], 0)
        self.assertEqual(result["summary"]["control_rows"], 4)
        for key, column in (("private_observations", "contrast"), ("private_anchors", "row_id"), ("private_genes", "gene")):
            self.assertEqual(len(result[key]), 0)
            self.assertIn(column, result[key])
        for mask in MASKS:
            self.assertIsNone(result["summary"]["masks"][mask]["contrast"])
            self.assertEqual(len(result["summary"]["masks"][mask]["ordered_plate_directions"]), 12)
        json.dumps(result["summary"], allow_nan=False)

    def test_one_incomplete_guide_pair_removed_without_dropping_supported_gene_pair(self):
        metadata, features = fixture()
        metadata, features = append_treatments(metadata, features, [
            ("E05", "GENE_A", "a3", "ACAC", [1, 0]),
        ])
        # a3 is unavailable on one physical plate, so a1/a3 and a2/a3 each
        # fail the all-12-directions rule. a1/a2 remains complete for GENE_A.
        keep = ~metadata.row_id.eq("p4-E05")
        result = analyze_crossguide(metadata[keep], features[keep])
        for mask in MASKS:
            summary = result["summary"]["masks"][mask]
            self.assertEqual(summary["input_guide_pairs"], 4)
            self.assertEqual(summary["complete_guide_pairs"], 2)
            self.assertEqual(summary["eligible_gene_groups"], 2)
            self.assertAlmostEqual(summary["contrast"], 1)

    def test_nontrivial_features_joint_shuffle_is_exactly_reproducible(self):
        metadata, features = fixture()
        features = np.random.default_rng(4).normal(size=(len(metadata), 7))
        baseline = analyze_crossguide(metadata, features)
        order = np.random.default_rng(44).permutation(len(metadata))
        shuffled = analyze_crossguide(metadata.iloc[order], features[order])
        self.assertEqual(baseline["summary"], shuffled["summary"])
        pd.testing.assert_frame_equal(baseline["private_observations"], shuffled["private_observations"])

    def test_mixed_recorded_condition_strata_fail(self):
        metadata, features = fixture()
        metadata.loc[metadata.plate.eq("p4"), "condition"] = "different stratum"
        with self.assertRaisesRegex(ValueError, "one recorded condition stratum"):
            analyze_crossguide(metadata, features)

    def test_paired_mask_difference_on_complete_gene_intersection(self):
        metadata, features = fixture()
        metadata, features = append_treatments(metadata, features, [
            ("A05", "GENE_C", "c1", "ACAC", [-1, 0]),
        ])
        result = analyze_crossguide(metadata, features)
        # The extra single-guide gene remains a reference. Primary excludes its
        # same-row well for A01: A's two orientations have contrasts 1 and 1.5.
        # Secondary has contrasts 1.5 and 1.5. B remains 1 in both masks.
        self.assertAlmostEqual(result["summary"]["masks"][MASKS[0]]["contrast"], 1.125)
        self.assertAlmostEqual(result["summary"]["masks"][MASKS[1]]["contrast"], 1.25)
        paired = result["summary"]["paired_mask_difference"]
        self.assertEqual(paired["intersection_gene_groups"], 2)
        self.assertFalse(paired["gene_cohort_composition_changed"])
        self.assertAlmostEqual(paired["contrast_difference"], 0.125)
        self.assertIn("composition can change", paired["interpretation"])


if __name__ == "__main__":
    unittest.main()
