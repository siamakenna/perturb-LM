"""Offline invented-data checks for the public annotation summary."""

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import query_info


def fixture():
    wells, ledger = [], []
    for layout in ("Target1", "Target2"):
        for sample, name, targets, key in (
            ("sample-a", "compound-a", "GENE2|GENE1", "key-a"),
            ("sample-b", "compound-b", "GENE1|GENE2|GENE1", "key-b"),
            ("sample-c", "compound-c", "GENE3", "key-c"),
        ):
            wells.append(dict(layout=layout, broad_sample=sample, InChIKey=key,
                              included_in_key_comparison="True"))
            ledger.append(dict(layout=layout, broad_sample=sample, pert_iname=name,
                               target_list=targets, InChIKey=key, status="unique_annotation"))
    return wells, ledger


class QueryInformationTests(unittest.TestCase):
    def test_canonicalization_and_aggregation(self):
        result = query_info._summarize(*fixture())
        self.assertEqual(result["shared_broad_sample_ids"], 3)
        self.assertEqual(result["raw_target_list_strings"]["distinct_groups"], 3)
        canonical = result["canonical_target_sets"]
        self.assertEqual(canonical["distinct_groups"], 2)
        self.assertEqual(canonical["singleton_groups_and_ids"], 1)
        self.assertEqual(canonical["ids_in_collision_groups"], 2)
        self.assertEqual(canonical["group_size_histogram"], {"1": 1, "2": 1})
        self.assertNotIn("sample-a", json.dumps(result))

    def test_cross_layout_annotation_changes_fail(self):
        for field in query_info.CHECK_FIELDS:
            with self.subTest(field=field):
                wells, ledger = fixture()
                ledger[3][field] += "-changed"
                with self.assertRaisesRegex(ValueError, "Cross-layout"):
                    query_info._summarize(wells, ledger)

    def test_duplicate_order_does_not_change_result(self):
        wells, ledger = fixture()
        duplicate = dict(ledger[0], status="identical_duplicate_collapsed")
        first = query_info._summarize(wells, [duplicate] + ledger)
        last = query_info._summarize(list(reversed(wells)), ledger + [duplicate])
        self.assertEqual(first, last)
        self.assertEqual(first["identical_duplicate_rows_collapsed"], 1)

    def test_conflicting_duplicate_fails(self):
        wells, ledger = fixture()
        ledger.append(dict(ledger[0], status="identical_duplicate_collapsed", target_list="OTHER"))
        with self.assertRaisesRegex(ValueError, "Duplicate annotation"):
            query_info._summarize(wells, ledger)

    def test_missing_labels_and_missing_tokens_excluded_separately(self):
        wells, ledger = fixture()
        for row in ledger:
            if row["broad_sample"] == "sample-a":
                row["target_list"] = "NA"
                row["pert_iname"] = ""
            elif row["broad_sample"] == "sample-b":
                row["target_list"] = "GENE1|unknown"
        result = query_info._summarize(wells, ledger)
        self.assertEqual(result["missing_target_annotations_by_raw_value"], {"NA": 1})
        self.assertEqual(result["target_lists_with_missing_tokens"], 1)
        self.assertEqual(result["target_annotation_coverage_ids"], 1)
        self.assertEqual(result["name_annotation_coverage_ids"], 2)
        self.assertEqual(result["missing_name_annotations_by_raw_value"], {"": 1})

    def test_only_included_intersection_used(self):
        wells, ledger = fixture()
        wells[0]["included_in_key_comparison"] = "False"
        result = query_info._summarize(wells, ledger)
        self.assertEqual(result["shared_broad_sample_ids"], 2)

    def test_missing_annotation_and_key_mismatch_fail(self):
        wells, ledger = fixture()
        with self.assertRaisesRegex(ValueError, "one unique annotation"):
            query_info._summarize(wells, ledger[1:])
        wells[0]["InChIKey"] = "wrong"
        with self.assertRaisesRegex(ValueError, "standardized keys"):
            query_info._summarize(wells, ledger)

    def test_empty_intersection_is_explicit(self):
        wells, ledger = fixture()
        for row in wells:
            row["included_in_key_comparison"] = "False"
        result = query_info._summarize(wells, ledger)
        self.assertEqual(result["shared_broad_sample_ids"], 0)
        self.assertEqual(result["canonical_target_sets"]["largest_group_size"], 0)

    def test_pinned_byte_verification_and_api(self):
        wells, ledger = fixture()
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(wells[0]))
        writer.writeheader()
        writer.writerows(wells)
        well_bytes = stream.getvalue().encode()
        ledger_bytes = json.dumps(ledger).encode()
        synthetic_hashes = {
            "layout_wells": hashlib.sha256(well_bytes).hexdigest(),
            "annotation_ledger": hashlib.sha256(ledger_bytes).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            layout_path, ledger_path = Path(tmp)/"wells.csv", Path(tmp)/"ledger.json"
            layout_path.write_bytes(well_bytes)
            ledger_path.write_bytes(ledger_bytes)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                query_info.analyze(layout_path, ledger_path)
            with patch.dict(query_info.EXPECTED_SHA256, synthetic_hashes):
                result = query_info.analyze(layout_path, ledger_path)
                self.assertEqual(result["source_sha256"], synthetic_hashes)
                self.assertEqual(result["shared_broad_sample_ids"], 3)
                ledger_path.write_bytes(ledger_bytes + b"\n")
                with self.assertRaisesRegex(ValueError, "annotation_ledger"):
                    query_info.analyze(layout_path, ledger_path)


if __name__ == "__main__":
    unittest.main()
