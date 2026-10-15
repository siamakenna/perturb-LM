"""Offline synthetic checks for the pilot's identity and candidate contract.

The invented identifiers and well layouts here are deliberately small.  None of
these tests asserts a scientific result or accesses the downloaded profiles.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("pilot_prepare", HERE / "prepare.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

TARGET1 = "BR00123523"
TARGET2 = "BR00121428"
PLATES = (TARGET1, TARGET2)


def registry():
    return {
        "JCP2022_033924": {
            "Metadata_JCP2022": "JCP2022_033924",
            "Metadata_pert_type": "negcon", "Metadata_Name": "DMSO",
            "Metadata_modality": "compound",
        },
        "JCP2022_999999": {
            "Metadata_JCP2022": "JCP2022_999999",
            "Metadata_pert_type": "empty", "Metadata_Name": "Empty",
            "Metadata_modality": "any",
        },
        "JCP2022_000099": {
            "Metadata_JCP2022": "JCP2022_000099",
            "Metadata_pert_type": "poscon", "Metadata_Name": "Synthetic control",
            "Metadata_modality": "compound",
        },
    }


def layout_row(well, broad, included=True, control="NA"):
    return {
        "well_position": well, "broad_sample": broad,
        "included_in_key_comparison": str(included),
        "control_type": control,
        "exclusion_reasons": "" if included else "control",
        "InChIKey": "AAAAAAAAAAAAAA-BBBBBBBBBB-C",
        "pert_type": "trt" if included else "poscon",
    }


def fixture():
    """Two shared identities, one unique identity in each plate, and controls."""
    layouts = {
        TARGET1: {
            "A01": layout_row("A01", "BRD-SYNTHETIC-A"),
            "A02": layout_row("A02", "BRD-SYNTHETIC-B"),
            "A03": layout_row("A03", "BRD-SYNTHETIC-C"),
            "A04": layout_row("A04", "", False),
            "A05": layout_row("A05", "BRD-SYNTHETIC-POS", False, "poscon_cp"),
        },
        TARGET2: {
            "B01": layout_row("B01", "BRD-SYNTHETIC-A"),
            "B02": layout_row("B02", "BRD-SYNTHETIC-B"),
            "B03": layout_row("B03", "BRD-SYNTHETIC-D"),
            "B04": layout_row("B04", "", False),
            "B05": layout_row("B05", "BRD-SYNTHETIC-POS", False, "poscon_cp"),
        },
    }
    annotations = {
        TARGET1: dict(zip(layouts[TARGET1], [
            "JCP2022_000001", "JCP2022_000002", "JCP2022_000003",
            "JCP2022_033924", "JCP2022_000099",
        ])),
        TARGET2: dict(zip(layouts[TARGET2], [
            "JCP2022_000001", "JCP2022_000002", "JCP2022_000004",
            "JCP2022_033924", "JCP2022_000099",
        ])),
    }
    observed = {plate: set(rows) for plate, rows in layouts.items()}
    return layouts, annotations, registry(), observed


def row_keys(rows):
    return {(row["plate"], row["well"]) for row in rows}


def all_retained(cohort):
    return cohort["gallery"] + cohort["queries"]


def move_well(inputs, plate, old, new):
    layouts, annotations, _, observed = inputs
    layouts[plate][new] = layouts[plate].pop(old)
    layouts[plate][new]["well_position"] = new
    annotations[plate][new] = annotations[plate].pop(old)
    observed[plate].remove(old)
    observed[plate].add(new)


class CohortIdentityTests(unittest.TestCase):
    def test_full_gallery_and_non_evaluable_queries_are_preserved(self):
        cohort, _ = m.build_cohort(*fixture())
        self.assertEqual({r["broad_sample"] for r in cohort["gallery"]},
                         {"BRD-SYNTHETIC-A", "BRD-SYNTHETIC-B", "BRD-SYNTHETIC-C"})
        self.assertEqual(len(cohort["queries"]), 3)
        by_id = {r["broad_sample"]: r for r in cohort["queries"]}
        self.assertEqual(by_id["BRD-SYNTHETIC-A"]["positive_gallery_wells"], ["A01"])
        self.assertEqual(by_id["BRD-SYNTHETIC-B"]["positive_gallery_wells"], ["A02"])
        self.assertEqual(by_id["BRD-SYNTHETIC-D"]["positive_gallery_wells"], [])
        self.assertFalse(by_id["BRD-SYNTHETIC-D"]["evaluable"])
        self.assertTrue(all(r["candidate_count"] == 3 for r in cohort["queries"]))

    def test_controls_not_candidates_and_dmso_separate(self):
        cohort, _ = m.build_cohort(*fixture())
        self.assertFalse(any(r["jcp2022"] in registry() for r in all_retained(cohort)))
        self.assertEqual(cohort["dmso_wells"][TARGET1], ["A04"])
        self.assertEqual(cohort["dmso_wells"][TARGET2], ["B04"])

    def test_registry_positive_at_treatment_position_is_excluded(self):
        inputs = fixture()
        for plate, well in ((TARGET1, "A05"), (TARGET2, "B05")):
            inputs[0][plate][well].update(included_in_key_comparison="True", control_type="NA")
        cohort, _ = m.build_cohort(*inputs)
        self.assertFalse(any(r["jcp2022"] == "JCP2022_000099" for r in all_retained(cohort)))
        self.assertTrue({(TARGET1, "A05"), (TARGET2, "B05")}.issubset(row_keys(cohort["exclusions"])))

    def test_layout_control_unlisted_in_registry_is_still_excluded(self):
        inputs = fixture()
        inputs[1][TARGET1]["A05"] = "JCP2022_000088"
        inputs[1][TARGET2]["B05"] = "JCP2022_000088"
        cohort, _ = m.build_cohort(*inputs)
        self.assertFalse(any(r["broad_sample"] == "BRD-SYNTHETIC-POS" for r in all_retained(cohort)))

    def test_explicit_control_label_overrides_stale_included_flag(self):
        inputs = fixture()
        inputs[0][TARGET1]["A03"].update(control_type="poscon_cp", included_in_key_comparison="True")
        cohort, _ = m.build_cohort(*inputs)
        self.assertNotIn((TARGET1, "A03"), row_keys(cohort["gallery"]))

    def test_nontreatment_type_overrides_stale_included_flag(self):
        inputs = fixture()
        inputs[0][TARGET1]["A03"]["pert_type"] = "negcon"
        cohort, _ = m.build_cohort(*inputs)
        self.assertNotIn((TARGET1, "A03"), row_keys(cohort["gallery"]))

    def test_same_broad_different_production_ids_does_not_create_positive(self):
        inputs = fixture()
        inputs[1][TARGET2]["B01"] = "JCP2022_000077"
        cohort, _ = m.build_cohort(*inputs)
        self.assertFalse(any(r["broad_sample"] == "BRD-SYNTHETIC-A" for r in all_retained(cohort)))
        self.assertTrue({(TARGET1, "A01"), (TARGET2, "B01")}.issubset(row_keys(cohort["exclusions"])))

    def test_distinct_broad_ids_sharing_jcp_are_not_merged(self):
        inputs = fixture()
        inputs[1][TARGET1]["A03"] = "JCP2022_000001"
        cohort, _ = m.build_cohort(*inputs)
        self.assertFalse(any(r["jcp2022"] == "JCP2022_000001" for r in all_retained(cohort)))
        self.assertTrue({(TARGET1, "A01"), (TARGET1, "A03"), (TARGET2, "B01")}.issubset(
            row_keys(cohort["exclusions"])))

    def test_sameplate_duplicate_identity_never_selects_arbitrary_row(self):
        inputs = fixture()
        inputs[0][TARGET1]["A06"] = layout_row("A06", "BRD-SYNTHETIC-A")
        inputs[1][TARGET1]["A06"] = "JCP2022_000001"
        inputs[3][TARGET1].add("A06")
        cohort, _ = m.build_cohort(*inputs)
        self.assertTrue({(TARGET1, "A01"), (TARGET1, "A06")}.issubset(row_keys(cohort["exclusions"])))
        self.assertFalse(any(r["broad_sample"] == "BRD-SYNTHETIC-A" for r in cohort["gallery"]))
        for row in cohort["queries"]:
            if row["broad_sample"] == "BRD-SYNTHETIC-A":
                self.assertFalse(row["evaluable"])

    def test_missing_production_annotation_cannot_be_imputed_from_broad_id(self):
        inputs = fixture()
        del inputs[1][TARGET2]["B01"]
        cohort, _ = m.build_cohort(*inputs)
        self.assertNotIn((TARGET2, "B01"), row_keys(all_retained(cohort)))
        self.assertIn((TARGET2, "B01"), row_keys(cohort["exclusions"]))

    def test_non_observed_profile_well_is_excluded(self):
        inputs = fixture()
        inputs[3][TARGET1].remove("A01")
        cohort, _ = m.build_cohort(*inputs)
        self.assertNotIn((TARGET1, "A01"), row_keys(cohort["gallery"]))
        queries = {r["broad_sample"]: r for r in cohort["queries"]}
        self.assertFalse(queries["BRD-SYNTHETIC-A"]["evaluable"])

    def test_identical_parent_key_does_not_define_exact_identity(self):
        cohort, _ = m.build_cohort(*fixture())
        self.assertEqual(sum(r["evaluable"] for r in cohort["queries"]), 2)
        self.assertTrue(all(len(r["positive_gallery_wells"]) <= 1 for r in cohort["queries"]))

    def test_same_coordinate_mask_removes_positive_and_candidate(self):
        inputs = fixture()
        move_well(inputs, TARGET2, "B01", "A01")
        cohort, _ = m.build_cohort(*inputs)
        query = next(r for r in cohort["queries"] if r["broad_sample"] == "BRD-SYNTHETIC-A")
        self.assertEqual(query["positive_gallery_wells"], [])
        self.assertEqual(query["candidate_count"], 2)
        self.assertFalse(query["evaluable"])

    def test_canonical_well_alias_does_not_bypass_same_coordinate_mask(self):
        inputs = fixture()
        move_well(inputs, TARGET2, "B01", "a1")
        cohort, _ = m.build_cohort(*inputs)
        query = next(r for r in cohort["queries"] if r["broad_sample"] == "BRD-SYNTHETIC-A")
        self.assertEqual(query["well"], "A01")
        self.assertFalse(query["evaluable"])
        self.assertEqual(query["candidate_count"], 2)

    def test_duplicate_canonical_positions_fail(self):
        inputs = fixture()
        inputs[0][TARGET1]["a1"] = layout_row("a1", "BRD-OTHER")
        inputs[1][TARGET1]["a1"] = "JCP2022_000098"
        inputs[3][TARGET1].add("a1")
        with self.assertRaises(ValueError):
            m.build_cohort(*inputs)

    def test_reordered_input_produces_identical_cohort_and_counts(self):
        inputs = fixture()
        expected = m.build_cohort(*inputs)
        layouts, annotations, controls, observed = copy.deepcopy(inputs)
        layouts = {p: dict(reversed(list(rows.items()))) for p, rows in reversed(list(layouts.items()))}
        annotations = {p: dict(reversed(list(rows.items()))) for p, rows in reversed(list(annotations.items()))}
        controls = dict(reversed(list(controls.items())))
        self.assertEqual(m.build_cohort(layouts, annotations, controls, observed), expected)

    def test_unknown_plate_cannot_silently_enter_cohort(self):
        inputs = fixture()
        inputs[0]["OTHER"] = {}
        inputs[1]["OTHER"] = {}
        inputs[3]["OTHER"] = set()
        with self.assertRaises(ValueError):
            m.build_cohort(*inputs)


class InputBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.paths = {}
        self.expected = {}
        directories = {
            "latest-public-layouts": self.root / "public",
            "latest-batch8-inspection": self.root / "pair",
            "latest-batch8-technical-qc": self.root / "qc",
            "latest-batch8-controls": self.root / "controls",
        }
        for name, directory in directories.items():
            directory.mkdir()
            (self.root / (name + ".txt")).write_text(str(directory) + "\n")
        for directory in (self.root / "public/audit", self.root / "pair/inspection",
                          self.root / "qc/results", self.root / "controls/results"):
            directory.mkdir()

        def add(name, relative, value):
            path = self.root / relative
            content = json.dumps(value).encode() if not isinstance(value, bytes) else value
            path.write_bytes(content)
            self.paths[name] = path
            self.expected[name] = (len(content), hashlib.sha256(content).hexdigest())

        add("layout", "public/audit/layout-wells_PRIVATE.csv", b"synthetic layout\n")
        add("annotation_ledger", "public/audit/annotation-ledger_PRIVATE.json", {})
        for plate in PLATES:
            add("profile_" + plate, "pair/inspection/" + plate + ".parquet", b"synthetic file " + plate.encode())
        add("well_metadata", "controls/results/well.csv.gz", b"synthetic metadata")
        add("control_registry", "controls/results/perturbation_control.csv", b"synthetic controls")
        add("inspection", "pair/inspection/batch8-pair-inspection.json", {
            "plates": [{"plate": plate, "download": {
                "local_sha256": self.expected["profile_" + plate][1]}} for plate in PLATES]})
        add("qc", "qc/results/batch8-technical-qc.json", {
            "prior_inspection_sha256": self.expected["inspection"][1],
            "layout_ledger_sha256": self.expected["layout"][1]})
        revision = "016e865fa0691244e0860943e41c7d6a88ed2580"
        add("controls", "controls/results/batch8-control-annotations.json", {
            "prior_qc_sha256": self.expected["qc"][1],
            "layout_sha256": self.expected["layout"][1], "revision": revision,
            "source_files": [{"path": source, "sha256": self.expected[name][1],
                              "bytes": self.expected[name][0], "revision": revision}
                             for source, name in (("metadata/well.csv.gz", "well_metadata"),
                                                  ("metadata/perturbation_control.csv", "control_registry"))]})
        patcher = mock.patch.dict(m.EXPECTED, self.expected, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_complete_bound_local_inputs_resolve(self):
        self.assertEqual(m.resolve_inputs(self.root), self.paths)

    def test_same_size_mutation_fails_hash_binding(self):
        path = self.paths["profile_" + TARGET1]
        path.write_bytes(b"X" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "changed or is missing"):
            m.resolve_inputs(self.root)

    def test_missing_file_fails_before_preparation(self):
        self.paths["well_metadata"].unlink()
        with self.assertRaisesRegex(ValueError, "changed or is missing"):
            m.resolve_inputs(self.root)

    def test_relative_or_multiple_recorded_locations_fail(self):
        pointer = self.root / "latest-public-layouts.txt"
        for text in ("public\n", str(self.root / "public") + "\n" + str(self.root / "pair")):
            with self.subTest(text=text):
                pointer.write_text(text)
                with self.assertRaisesRegex(ValueError, "Invalid recorded location"):
                    m.resolve_inputs(self.root)

    def test_provenance_link_is_checked_independently_of_file_hash(self):
        path = self.paths["controls"]
        report = json.loads(path.read_text())
        report["prior_qc_sha256"] = "0" * 64
        path.write_text(json.dumps(report))
        m.EXPECTED["controls"] = (path.stat().st_size, m.sha256(path))
        with self.assertRaisesRegex(ValueError, "provenance links"):
            m.resolve_inputs(self.root)

    def test_existing_output_is_not_overwritten(self):
        out = self.root / "existing"
        out.mkdir()
        sentinel = out / "keep.txt"
        sentinel.write_text("keep existing work\n")
        with self.assertRaises(FileExistsError):
            m.prepare(self.root, out)
        self.assertEqual(sentinel.read_text(), "keep existing work\n")
        self.assertEqual(list(out.iterdir()), [sentinel])


if __name__ == "__main__":
    unittest.main()
