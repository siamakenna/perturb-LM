"""Small synthetic metadata tests; no real cohorts, scores, or models (#30, #52)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from perturb_lm.audits.cohort import read_table
from perturb_lm.audits.rotations import PLATES, plan_rotations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/phase5_1/rotation_mapping_synthetic.csv"
SCRIPT = ROOT / "scripts/plan_phase5_1_rotations.py"


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.rows = read_table(FIXTURE)

    def plan(self, rows=None, **kwargs):
        options = dict(
            min_train_groups=3,
            min_evaluable_groups=2,
            upstream_normalization_scope="source_batch_global",
        )
        options.update(kwargs)
        return plan_rotations(self.rows if rows is None else rows, **options)

    def test_all_ordered_rotations_and_effective_units(self):
        result, manifest = self.plan()
        self.assertEqual(result["candidate_rotations"], 12)
        self.assertEqual(result["design_eligible_rotations"], 12)
        self.assertEqual(len(manifest), 12 * len(self.rows))
        self.assertEqual(result["status"], "PROPOSED_NOT_APPROVED")
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["selected_noncontrol_population"]["reagents"], 3)
        self.assertEqual(result["selected_noncontrol_population"]["gene_annotation_groups"], 2)
        pairs = set()
        for rotation in result["rotations"]:
            q, g = rotation["query_plate"], rotation["gallery_plate"]
            pairs.add((q, g))
            self.assertEqual(set(rotation["training_plates"]), set(PLATES) - {q, g})
            self.assertFalse(rotation["execution_allowed"])
            self.assertEqual(rotation["query_population"]["profile_rows"], 4)
            self.assertEqual(rotation["evaluable"]["profile_rows"], 3)
            self.assertEqual(rotation["evaluable"]["reagents"], 2)
            self.assertEqual(rotation["evaluable"]["gene_annotation_groups"], 1)
            self.assertEqual(rotation["unevaluable_queries"], 1)
        self.assertEqual(len(pairs), 12)

    def test_full_gallery_controls_missing_labels_and_coordinate_masks(self):
        result, manifest = self.plan()
        rotation = result["rotations"][0]
        records = manifest[manifest.rotation_id.eq(rotation["rotation_id"])]
        gallery = records[records.role.eq("gallery")]
        self.assertEqual(set(gallery.reagent), {"SYNTH_TREAT_A", "SYNTH_TREAT_B", "SYNTH_TREAT_C"})
        self.assertEqual(len(gallery), 4)  # Includes the unrecoverable fixed-coordinate B.
        self.assertEqual(rotation["query_plate_controls_excluded"], 1)
        self.assertEqual(rotation["query_plate_missing_labels_excluded"], 1)
        queries = records[records.role.eq("query")]
        for query in queries.itertuples():
            positives = gallery[gallery.record_id.isin(json.loads(query.positive_record_ids))]
            self.assertTrue(positives.well.ne(query.well).all())
            self.assertTrue(positives.plate.ne(query.plate).all())
            self.assertTrue(positives.reagent.eq(query.reagent).all())
            self.assertEqual(query.candidate_count, int(gallery.well.ne(query.well).sum()))
            self.assertEqual(
                query.candidate_reagent_count,
                gallery.loc[gallery.well.ne(query.well), "reagent"].nunique(),
            )
            self.assertEqual(query.positive_reagent_count, int(query.positive_count > 0))
            if query.reagent == "SYNTH_TREAT_B":
                self.assertFalse(query.evaluable)
                self.assertEqual(query.positive_count, 0)
        self.assertEqual(rotation["positive_reagent_count_histogram"], {"0": 1, "1": 3})
        self.assertEqual(rotation["candidate_reagent_count_histogram"], {"2": 1, "3": 3})

    def test_seen_treatment_excludes_and_reports_unseen_reagent(self):
        # C occurs only on the query/gallery pair for two rotations.
        subset = self.rows[
            ~(
                self.rows.Assay_Plate_Barcode.isin(PLATES[2:])
                & self.rows.broad_sample.eq("SYNTH_TREAT_C")
            )
        ]
        result, manifest = self.plan(subset, min_train_groups=2, min_evaluable_groups=1)
        rotation = result["rotations"][0]
        self.assertEqual(
            rotation["exclusion_reason_counts_nonexclusive"]["reagent_not_seen_in_training"], 1
        )
        self.assertEqual(rotation["unseen_query_reagent_groups"], 1)
        query = manifest[
            manifest.rotation_id.eq(rotation["rotation_id"])
            & manifest.role.eq("query")
            & manifest.reagent.eq("SYNTH_TREAT_C")
        ].iloc[0]
        self.assertGreater(query.positive_count, 0)
        self.assertFalse(query.evaluable)
        self.assertEqual(rotation["evaluable"]["reagents"], 1)

    def test_no_positives_never_passes_design_gate(self):
        rows = self.rows[self.rows.broad_sample.eq("SYNTH_TREAT_B")]
        result, _ = self.plan(rows, min_train_groups=1, min_evaluable_groups=1)
        self.assertEqual(result["design_eligible_rotations"], 0)
        self.assertTrue(
            all("zero_evaluable_queries" in r["design_blockers"] for r in result["rotations"])
        )

    def test_explicit_positive_minimums_and_threshold_failures(self):
        for key in ("min_train_groups", "min_evaluable_groups"):
            for value in (0, -1, True, 1.5):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.plan(**{key: value})
        for key in ("min_train_groups", "min_evaluable_groups"):
            result, _ = self.plan(**{key: 20})
            self.assertEqual(result["design_eligible_rotations"], 0)
        with self.assertRaises(TypeError):
            plan_rotations(self.rows)

    def test_empty_query_gallery_and_training_populations_remain_blocked_plans(self):
        rows = self.rows[self.rows.Metadata_pert_type.ne("trt")]
        result, manifest = self.plan(rows)
        self.assertEqual(result["design_eligible_rotations"], 0)
        self.assertTrue(manifest.role.eq("excluded").all())
        for rotation in result["rotations"]:
            self.assertIn("empty_noncontrol_gallery", rotation["design_blockers"])
            self.assertIn("zero_evaluable_queries", rotation["design_blockers"])
            self.assertEqual(rotation["query_population"]["profile_rows"], 0)

    def test_heldout_policies_fail_closed(self):
        for policy in ("heldout_treatment", "heldout_gene", "pretend_independent"):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "heldout"):
                self.plan(split_policy=policy)

    def test_all_supported_normalization_scopes_block_execution(self):
        for scope in ("unknown", "source_batch_global"):
            result, _ = self.plan(upstream_normalization_scope=scope)
            self.assertFalse(result["execution_allowed"])
            expected = (
                "upstream_normalization_unknown"
                if scope == "unknown"
                else "source_batch_preprocessing_is_transductive"
            )
            self.assertIn(expected, result["execution_blockers"])
        with self.assertRaises(ValueError):
            self.plan(upstream_normalization_scope="train_only_verified")

    def test_control_boolean_strings_are_parsed_not_truthy(self):
        rows = self.rows.assign(
            is_control=self.rows.Metadata_pert_type.ne("trt").map({True: "True", False: "False"})
        )
        result, _ = self.plan(rows)
        self.assertEqual(result["selected_control_rows_with_labels"], 4)
        for value in ("maybe", "", "True"):
            changed = rows.copy()
            changed.loc[0, "is_control"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(changed)

    def test_missing_ambiguous_and_conflicting_metadata_fail_closed(self):
        mutations = {
            "record_id": "",
            "Batch": "wrong",
            "well_position": "A1",
            "resolved": "False",
            "experiment_status": "ambiguous",
            "barcode_status": "unmatched",
            "well_status": "ambiguous",
            "sample_status": "conflict",
            "annotation_status": "ambiguous",
            "map_conflict": "True",
            "batch_path_conflict": "True",
            "identity_annotation_conflict": "True",
            "duplicate_plate_well": "True",
            "Metadata_pert_type": "",
            "Antibiotics": "Puromycin",
            "Anomaly": "",
        }
        for field, value in mutations.items():
            changed = self.rows.copy()
            changed.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.plan(changed)
        for field in ("Metadata_gene", "resolved", "Cell_line"):
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, "Missing mapping"):
                self.plan(self.rows.drop(columns=field))

    def test_duplicate_record_or_plate_well_is_rejected(self):
        for change_id in (False, True):
            extra = self.rows.iloc[[0]].copy()
            if change_id:
                extra["record_id"] = "SYNTH_OTHER_RECORD"
            with self.subTest(change_id=change_id), self.assertRaisesRegex(ValueError, "Duplicate"):
                self.plan(pd.concat([self.rows, extra], ignore_index=True))

    def test_contradictory_alias_and_duplicate_columns_are_rejected(self):
        rows = self.rows.assign(Metadata_broad_sample=self.rows.broad_sample)
        rows.loc[0, "Metadata_broad_sample"] = "SYNTH_WRONG_ID"
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            self.plan(rows)
        with self.assertRaisesRegex(ValueError, "Duplicate input column"):
            self.plan(pd.concat([self.rows, self.rows[["record_id"]]], axis=1))

    def test_incomplete_plate_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "All four"):
            self.plan(self.rows[self.rows.Assay_Plate_Barcode.ne(PLATES[-1])])

    def test_both_assigned_training_plates_need_noncontrol_rows(self):
        rows = self.rows[
            ~(self.rows.Assay_Plate_Barcode.eq(PLATES[-1]) & self.rows.Metadata_pert_type.eq("trt"))
        ]
        result, _ = self.plan(rows)
        rotation = result["rotations"][0]
        self.assertEqual(rotation["training"]["reagents"], 3)
        self.assertEqual(rotation["training"]["plates"], 1)
        self.assertFalse(rotation["design_eligible"])
        self.assertIn("missing_training_plate_population", rotation["design_blockers"])
        self.assertEqual(rotation["training_plates_without_noncontrol_rows"], [PLATES[-1]])

    def test_well_alias_is_canonicalized_and_conflicting_batch_aliases_fail(self):
        rows = self.rows.assign(Metadata_Well=self.rows.well_position.str.lower())
        rows.loc[0, "Metadata_Well"] = "a1"
        self.plan(rows)
        rows.loc[0, "Metadata_Well"] = "A03"
        with self.assertRaisesRegex(ValueError, "Metadata_Well"):
            self.plan(rows)
        for alias in ("Metadata_Batch", "Metadata_batch", "path_batch"):
            rows = self.rows.assign(**{alias: ""})
            self.plan(rows)  # An empty optional alias adds no contradictory evidence.
            rows.loc[0, alias] = "SYNTH_WRONG_BATCH"
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, alias):
                self.plan(rows)

    def test_source_mapping_and_control_aliases_cannot_bypass_conflict_flags(self):
        for alias, original in (
            ("mapped_sample", "broad_sample"),
            ("control_type", "Metadata_control_type"),
            ("negcon_control_type", "Metadata_negcon_control_type"),
        ):
            rows = self.rows.copy()
            if original not in rows:
                rows[original] = ""
            rows[alias] = rows[original]
            self.plan(rows)
            rows.loc[0, alias] = "SYNTH_CONFLICT"
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, alias):
                self.plan(rows)

    def test_outside_cohort_is_explicit_and_missing_genes_not_imputed(self):
        extra = self.rows.iloc[[0]].assign(
            record_id="SYNTH_OUTSIDE", Assay_Plate_Barcode="SYNTH_OTHER_PLATE"
        )
        rows = pd.concat([self.rows, extra], ignore_index=True)
        rows.loc[rows.broad_sample.eq("SYNTH_TREAT_C"), "Metadata_gene"] = ""
        result, _ = self.plan(rows)
        self.assertEqual(result["out_of_scope_rows"], 1)
        self.assertEqual(result["selected_noncontrol_population"]["reagents_missing_gene"], 1)
        self.assertEqual(result["selected_noncontrol_population"]["rows_missing_gene"], 4)

    def test_deterministic_under_row_shuffle(self):
        a, ma = self.plan()
        b, mb = self.plan(self.rows.sample(frac=1, random_state=17))
        self.assertEqual(a, b)
        pd.testing.assert_frame_equal(ma, mb)

    def test_cli_smoke_is_synthetic_and_private(self):
        output_root = ROOT / "outputs"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="rotation-test-", dir=output_root) as directory:
            out = Path(directory) / "new-output"
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--synthetic-fixture",
                    "--out",
                    str(out),
                    "--min-train-groups",
                    "3",
                    "--min-evaluable-groups",
                    "2",
                    "--upstream-normalization-scope",
                    "source_batch_global",
                ],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((out / "rotation-plan.json").read_text())
            self.assertEqual(summary["evidence_kind"], "synthetic_fixture")
            self.assertFalse(summary["execution_allowed"])
            self.assertNotIn(str(ROOT), json.dumps(summary))
            self.assertEqual((out / "rotation-manifest_PRIVATE.csv").stat().st_mode & 0o077, 0)
            self.assertEqual(summary["candidate_rotations"], 12)

    def test_output_guard_rejects_existing_or_outside_and_symlink_escape(self):
        spec = importlib.util.spec_from_file_location("phase51_rotation_cli", SCRIPT)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ValueError):
                cli.guarded_output(Path(outside) / "new", ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as directory:
            with self.assertRaises(ValueError):
                cli.guarded_output(Path(directory), ROOT)
            escape = Path(directory) / "escape"
            escape.symlink_to(ROOT / "docs", target_is_directory=True)
            with self.assertRaises(ValueError):
                cli.guarded_output(escape / "new", ROOT)


if __name__ == "__main__":
    unittest.main()
