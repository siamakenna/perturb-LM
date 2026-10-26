"""Synthetic-only checks for the new Phase 5.3 information audit."""

import json
import math
import unittest

import pandas as pd

from query_audit import REQUIRED_COLUMNS, analyze_query_information


def synthetic_frame(specifications):
    rows = []
    for number, specification in enumerate(specifications):
        row = {
            "row_id": f"SYNTH_ROW_{number}",
            "plate": "SYNTH_PLATE_PRIVATE",
            "well": f"A{number + 1:02d}",
            "gene": f"SYNTH_GENE_{number}",
            "reagent": f"SYNTH_REAGENT_{number}",
            "sequence": f"SYNTH_SEQUENCE_PRIVATE_{number}",
            "condition": "SYNTH_CONDITION_PRIVATE",
            "treatment": True,
            "control": False,
            "pert_type": "SYNTH_CATEGORY_PRIVATE",
            "control_type": "SYNTH_CONTROL_PRIVATE",
            "negcon_control_type": "SYNTH_NEGCON_PRIVATE",
        }
        row.update(specification)
        rows.append(row)
    return pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))


class QueryInformationAuditTests(unittest.TestCase):
    def test_two_equal_collision_groups_have_known_entropy(self):
        data = synthetic_frame([
            {"pert_type": "SYNTH_CATEGORY_A"},
            {"pert_type": "SYNTH_CATEGORY_A"},
            {"pert_type": "SYNTH_CATEGORY_B"},
            {"pert_type": "SYNTH_CATEGORY_B"},
        ])
        result = analyze_query_information(data)["summary"]
        category = result["descriptions"]["category_only"]
        self.assertEqual(category["analyzed_unique_reagent_count"], 4)
        self.assertEqual(category["distinct_signature_count"], 2)
        self.assertEqual(category["conditional_identity_entropy_bits"], 1.0)
        self.assertEqual(category["tie_only_expected_exact_identity_hit_at_1"], 0.5)
        self.assertEqual(category["fraction_reagents_with_unique_signature"], 0.0)
        self.assertEqual(category["minimum_collision_group_size"], 2)
        self.assertEqual(category["maximum_collision_group_size"], 2)
        gene = result["descriptions"]["gene_aware"]
        self.assertEqual(gene["distinct_signature_count"], 4)
        self.assertEqual(gene["conditional_identity_entropy_bits"], 0.0)
        self.assertEqual(gene["fraction_reagents_with_unique_signature"], 1.0)
        self.assertIsNone(gene["minimum_collision_group_size"])

    def test_unequal_collision_groups_have_known_entropy(self):
        data = synthetic_frame([
            {"pert_type": "SYNTH_SINGLETON"},
            {"pert_type": "SYNTH_TRIPLE"},
            {"pert_type": "SYNTH_TRIPLE"},
            {"pert_type": "SYNTH_TRIPLE"},
        ])
        category = analyze_query_information(data)["summary"]["descriptions"]["category_only"]
        self.assertAlmostEqual(category["conditional_identity_entropy_bits"], 0.75 * math.log2(3))
        self.assertEqual(category["tie_only_expected_exact_identity_hit_at_1"], 0.5)
        self.assertEqual(category["fraction_reagents_with_unique_signature"], 0.25)
        self.assertEqual(category["minimum_equivalence_class_size"], 1)
        self.assertEqual(category["maximum_equivalence_class_size"], 3)
        self.assertEqual(category["minimum_collision_group_size"], 3)

    def test_repeated_wells_do_not_add_independent_reagent_identities(self):
        data = synthetic_frame([{}, {}, {"pert_type": "SYNTH_SECOND_CATEGORY"}])
        original = analyze_query_information(data)["summary"]
        replicate = data.iloc[[0]].copy()
        replicate["row_id"] = "SYNTH_REPLICATE_ROW"
        replicate["plate"] = "SYNTH_SECOND_PLATE"
        replicate["well"] = "B01"
        repeated = analyze_query_information(pd.concat([data, replicate, replicate], ignore_index=True))["summary"]
        self.assertEqual(original["descriptions"], repeated["descriptions"])
        self.assertEqual(repeated["input_accounting"]["treatment_unique_reagent_count"], 3)
        self.assertEqual(repeated["input_accounting"]["treatment_row_count"], 5)

    def test_same_gene_multiple_guides_remain_exact_identity_collision(self):
        data = synthetic_frame([
            {"gene": "SYNTH_SAME_RECORDED_GENE"},
            {"gene": "SYNTH_SAME_RECORDED_GENE"},
        ])
        gene = analyze_query_information(data)["summary"]["descriptions"]["gene_aware"]
        self.assertEqual(gene["distinct_signature_count"], 1)
        self.assertEqual(gene["collision_reagent_count"], 2)
        self.assertEqual(gene["conditional_identity_entropy_bits"], 1.0)
        self.assertEqual(gene["tie_only_expected_exact_identity_hit_at_1"], 0.5)

    def test_missing_categoricals_are_counted_and_tagged(self):
        data = synthetic_frame([
            {"pert_type": None, "control_type": pd.NA},
            {"pert_type": float("nan"), "control_type": "  "},
            {"pert_type": "missing", "control_type": "missing"},
        ])
        result = analyze_query_information(data)["summary"]
        for field in ("pert_type", "control_type"):
            self.assertEqual(result["missing_category_accounting"][field], {
                "treatment_row_count": 2,
                "unique_reagent_count_with_any_missing": 2,
                "unique_reagent_count_with_all_missing": 2,
            })
        category = result["descriptions"]["category_only"]
        self.assertEqual(category["distinct_signature_count"], 2)
        self.assertEqual(category["equivalence_class_size_histogram"], [
            {"class_size": 1, "signature_count": 1, "reagent_count": 1},
            {"class_size": 2, "signature_count": 1, "reagent_count": 2},
        ])

    def test_unknown_gene_does_not_create_biological_annotation(self):
        data = synthetic_frame([
            {"gene": None}, {"gene": "  "}, {"gene": "missing"},
        ])
        result = analyze_query_information(data)["summary"]
        self.assertEqual(result["gene_annotation_accounting"]["missing"]["treatment_row_count"], 2)
        gene = result["descriptions"]["gene_aware"]
        self.assertEqual(gene["distinct_signature_count"], 2)
        self.assertEqual(gene["collision_reagent_count"], 2)
        self.assertIn("not a biological", analyze_query_information.__doc__)

    def test_well_like_gene_is_preserved_and_flagged_without_invalidation(self):
        data = synthetic_frame([
            {"gene": "F10", "well": "F10"},
            {"gene": "SYNTH_DISTINCT_LITERAL"},
        ])
        result = analyze_query_information(data)
        accounting = result["summary"]["gene_annotation_accounting"]
        self.assertEqual(accounting["treatment_rows_with_well_like_recorded_gene"], 1)
        self.assertEqual(accounting["treatment_rows_with_gene_matching_recorded_well"], 1)
        self.assertTrue(accounting["well_like_values_are_unresolved_identifier_ambiguities_not_invalid_genes"])
        self.assertEqual(result["summary"]["descriptions"]["gene_aware"]["distinct_signature_count"], 2)
        self.assertIn("F10", " ".join(result["private_collision_ledger"]["recorded_gene_values_json"]))
        self.assertNotIn("F10", json.dumps(result["summary"]))

    def test_source_order_does_not_change_summary_or_private_ledger_order(self):
        data = synthetic_frame([{}, {"gene": None}, {"pert_type": None}, {}])
        repeated = data.iloc[[0]].copy()
        repeated["row_id"] = "SYNTH_REPLICATED_ROW"
        data = pd.concat([data, repeated], ignore_index=True)
        first = analyze_query_information(data)
        second = analyze_query_information(data.sample(frac=1, random_state=53))
        self.assertEqual(first["summary"], second["summary"])
        pd.testing.assert_frame_equal(first["private_collision_ledger"], second["private_collision_ledger"])

    def test_public_summary_contains_no_source_values_or_signature_hashes(self):
        data = synthetic_frame([{}, {}])
        result = analyze_query_information(data)
        public = json.dumps(result["summary"], allow_nan=False)
        for field in ("gene", "reagent", "sequence", "condition", "plate", "pert_type", "control_type", "negcon_control_type"):
            for source_value in data[field].dropna().unique():
                self.assertNotIn(source_value, public)
        for digest in result["private_collision_ledger"]["signature_sha256"]:
            self.assertNotIn(digest, public)
        self.assertFalse(result["summary"]["predictive_query_renderer_called"])
        self.assertFalse(result["summary"]["historical_641_query_results_recomputed"])
        self.assertEqual(result["summary"]["encoder_queries_generated"], 0)
        self.assertEqual(result["summary"]["model_runs"], 0)

    def test_conflicting_annotations_are_not_arbitrarily_resolved(self):
        data = synthetic_frame([
            {"reagent": "SYNTH_CONFLICTING_REAGENT", "gene": "SYNTH_GENE_A"},
            {"reagent": "SYNTH_CONFLICTING_REAGENT", "gene": "SYNTH_GENE_B"},
            {"reagent": "SYNTH_CONSISTENT_REAGENT", "gene": "SYNTH_GENE_C"},
        ])
        result = analyze_query_information(data)
        category = result["summary"]["descriptions"]["category_only"]
        gene = result["summary"]["descriptions"]["gene_aware"]
        self.assertEqual(category["analyzed_unique_reagent_count"], 2)
        self.assertEqual(category["excluded_conflicting_unique_reagent_count"], 0)
        self.assertEqual(gene["analyzed_unique_reagent_count"], 1)
        self.assertEqual(gene["excluded_conflicting_unique_reagent_count"], 1)
        self.assertEqual(gene["excluded_conflicting_treatment_row_count"], 2)
        ledger = result["private_collision_ledger"]
        conflicted = ledger[(ledger.description == "gene_aware") & ledger.reagent_has_conflicting_signatures]
        self.assertEqual(len(conflicted), 2)
        self.assertFalse(conflicted.included_in_identity_metrics.any())

    def test_treatment_selection_controls_and_missing_reagent_accounting(self):
        data = synthetic_frame([
            {},
            {"treatment": "false", "control": "true"},
            {"treatment": None, "control": None},
            {"reagent": None},
        ])
        result = analyze_query_information(data)["summary"]
        accounting = result["input_accounting"]
        self.assertEqual(accounting["row_count"], 4)
        self.assertEqual(accounting["treatment_row_count"], 2)
        self.assertEqual(accounting["control_row_count"], 1)
        self.assertEqual(accounting["rows_with_missing_treatment_flag"], 1)
        self.assertEqual(accounting["rows_with_missing_control_flag"], 1)
        self.assertEqual(accounting["treatment_rows_with_missing_reagent"], 1)
        self.assertEqual(accounting["treatment_unique_reagent_count"], 1)

    def test_empty_treatment_population_has_undefined_ratios_not_nan(self):
        result = analyze_query_information(synthetic_frame([]))
        json.dumps(result["summary"], allow_nan=False)
        for description in result["summary"]["descriptions"].values():
            self.assertEqual(description["analyzed_unique_reagent_count"], 0)
            self.assertEqual(description["distinct_signature_count"], 0)
            self.assertIsNone(description["conditional_identity_entropy_bits"])
            self.assertIsNone(description["tie_only_expected_exact_identity_hit_at_1"])
        self.assertTrue(result["private_collision_ledger"].empty)

    def test_input_validation_and_no_mutation(self):
        data = synthetic_frame([{}])
        unchanged = data.copy(deep=True)
        analyze_query_information(data)
        pd.testing.assert_frame_equal(data, unchanged)
        with self.assertRaisesRegex(ValueError, "Missing required metadata columns"):
            analyze_query_information(data.drop(columns=["gene"]))
        bad = data.copy(deep=True)
        bad["treatment"] = bad["treatment"].astype(object)
        bad.loc[0, "treatment"] = "not-an-explicit-boolean"
        with self.assertRaisesRegex(ValueError, "explicit boolean"):
            analyze_query_information(bad)


if __name__ == "__main__":
    unittest.main()
