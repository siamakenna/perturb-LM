"""Invented A549 metadata only; preserve the existing U2OS validator."""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import pandas as pd

import a549_validation as a549
from perturb_lm.audits import rotations


def fixture():
    records = []
    conditions = {
        "Perturbation": "crispr", "Cell_type": "A549", "Time": "144",
        "Density": "100", "Antibiotics": "absent", "Cell_line": "Cas9",
        "Time_delay": "Day0", "Times_imaged": "1", "Anomaly": "none",
    }
    for p, plate in enumerate(a549.PLATES):
        for i, well in enumerate(("A01", "B02")):
            row = {name: "" for name in a549.REQUIRED}
            row.update(record_id=f"SYNTH_{p}_{i}", Batch=a549.BATCH,
                       Assay_Plate_Barcode=plate, well_position=well,
                       broad_sample=f"SYNTH_R{i}", Metadata_pert_type="trt",
                       Metadata_gene=f"SYNTH_GENE_{i}", resolved="True",
                       experiment_status="matched", barcode_status="matched",
                       well_status="matched", sample_status="matched", annotation_status="matched",
                       **conditions, **{name: "False" for name in a549.CONFLICTS})
            records.append(row)
    return pd.DataFrame(records)


class A549ValidationTests(unittest.TestCase):
    def test_exact_stratum_and_all_original_rows_are_preserved(self):
        original = fixture()
        before = original.copy(deep=True)
        actual = a549.validate_a549_mapping(original)
        pd.testing.assert_frame_equal(original, before)
        self.assertEqual(len(actual), 8)
        self.assertEqual(set(actual.Assay_Plate_Barcode), set(a549.PLATES))
        self.assertFalse(actual.is_control.any())
        self.assertTrue(actual.Cell_type.eq("A549").all())
        self.assertTrue(actual.Anomaly.eq("none").all())

    def test_u2os_wga_puromycin_and_wrong_conditions_are_rejected(self):
        for field, value in (("Cell_type", "U2OS"), ("Anomaly", "WGA"),
                             ("Antibiotics", "Puromycin"), ("Time", "96"),
                             ("Density", "80"), ("Cell_line", "Parental"),
                             ("Time_delay", "Day1"), ("Times_imaged", "2"),
                             ("Perturbation", "orf")):
            with self.subTest(field=field):
                rows = fixture()
                rows[field] = value
                with self.assertRaises(ValueError):
                    a549.validate_a549_mapping(rows)

    def test_mixed_or_missing_conditions_are_rejected(self):
        for value in ("96", ""):
            rows = fixture()
            rows.loc[0, "Time"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                a549.validate_a549_mapping(rows)

    def test_puromycin_plate_ids_and_extra_or_missing_plates_are_rejected(self):
        for plate in ("BR00117001", "BR00117002", "BR00116996"):
            rows = fixture()
            rows.loc[0, "Assay_Plate_Barcode"] = plate
            with self.subTest(plate=plate), self.assertRaises(ValueError):
                a549.validate_a549_mapping(rows)
        with self.assertRaises(ValueError):
            a549.validate_a549_mapping(fixture().iloc[:-2])

    def test_physical_keys_canonical_wells_and_aliases_remain_guarded(self):
        rows = fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate physical"):
            a549.validate_a549_mapping(pd.concat([rows, rows.iloc[[0]].assign(record_id="SYNTH_DUP")]))
        for well in ("A1", "A00", "Q01", "A25"):
            rows = fixture()
            rows.loc[0, "well_position"] = well
            with self.subTest(well=well), self.assertRaises(ValueError):
                a549.validate_a549_mapping(rows)
        rows = fixture()
        rows["Metadata_Plate"] = rows.Assay_Plate_Barcode
        rows.loc[0, "Metadata_Plate"] = "BR00117001"
        with self.assertRaisesRegex(ValueError, "identity annotation"):
            a549.validate_a549_mapping(rows)
        rows = fixture()
        rows["Metadata_Well"] = rows.well_position
        rows.loc[0, "Metadata_Well"] = "A1"
        self.assertEqual(len(a549.validate_a549_mapping(rows)), 8)
        rows.loc[0, "Metadata_Well"] = "C03"
        with self.assertRaisesRegex(ValueError, "Metadata_Well"):
            a549.validate_a549_mapping(rows)

    def test_resolved_join_statuses_and_conflict_flags_remain_guarded(self):
        changes = [(name, "True") for name in a549.CONFLICTS]
        changes += [("resolved", "False"), ("resolved", "unknown")]
        changes += [(name, "unmatched") for name in
                    ("experiment_status", "barcode_status", "well_status", "sample_status", "annotation_status")]
        for name, value in changes:
            rows = fixture()
            rows.loc[0, name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                a549.validate_a549_mapping(rows)

    def test_control_booleans_are_explicit_and_cannot_contradict_categories(self):
        rows = fixture()
        rows["is_control"] = "False"
        self.assertFalse(a549.validate_a549_mapping(rows).is_control.any())
        for value in ("True", "unknown"):
            rows.loc[0, "is_control"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                a549.validate_a549_mapping(rows)

    def test_reagent_gene_and_batch_alias_contradictions_are_rejected(self):
        rows = fixture()
        rows.loc[0, "Metadata_gene"] = "SYNTH_OTHER_GENE"
        with self.assertRaisesRegex(ValueError, "inconsistent gene"):
            a549.validate_a549_mapping(rows)
        rows = fixture()
        rows["path_batch"] = rows.Batch
        rows.loc[0, "path_batch"] = "SYNTH_OTHER_BATCH"
        with self.assertRaisesRegex(ValueError, "path_batch"):
            a549.validate_a549_mapping(rows)

    def test_original_u2os_validator_is_separate_and_unchanged(self):
        source = Path(rotations.__file__)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        original_plates = tuple(f"BR0011699{i}" for i in range(6, 10))
        self.assertEqual(rotations.PLATES, original_plates)
        with self.assertRaises(ValueError):
            rotations._validate(fixture())
        converted = fixture()
        converted["Assay_Plate_Barcode"] = converted.Assay_Plate_Barcode.map(dict(zip(a549.PLATES, original_plates)))
        converted["Cell_type"] = "U2OS"
        converted["Anomaly"] = "WGA"
        self.assertEqual(len(rotations._validate(converted)), 8)
        with self.assertRaises(ValueError):
            a549.validate_a549_mapping(converted)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        self.assertEqual(rotations.PLATES, original_plates)


if __name__ == "__main__":
    unittest.main()
