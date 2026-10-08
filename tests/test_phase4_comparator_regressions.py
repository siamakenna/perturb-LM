"""Synthetic regression tests using only unittest and NumPy.

Run without pytest or TIFF dependencies:
    python -m unittest discover -s tests -p test_phase4_comparator_regressions.py -v
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comparator_tools as c


class ComparatorRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scores = self.root / "scores.tsv"
        self.output = self.root / "output"

    def summarize(self, text):
        self.scores.write_text(text, encoding="utf-8")
        return c.scores_summary(
            self.scores, self.output, "method", "query_id", "evaluable",
            "average_precision", "synthetic-regression", "\t",
        )

    def test_valid_scores_preserve_coverage_means_and_pairing(self):
        report = self.summarize(
            "method\tquery_id\tevaluable\taverage_precision\n"
            "a\tq1\ttrue\t0.8\na\tq2\tfalse\t\na\tq3\ttrue\t0.2\n"
            "b\tq3\ttrue\t0.1\nb\tq2\tfalse\t\nb\tq1\ttrue\t0.4\n"
        )
        self.assertAlmostEqual(report["coverage"], 2 / 3)
        self.assertEqual(report["conditional_mean_by_method"], {"a": 0.5, "b": 0.25})
        self.assertEqual(report["paired_mean_differences"][0]["mean_paired_difference_left_minus_right"], 0.25)
        self.assertTrue((self.output / "analysis-complete.json").is_file())

    def test_extra_named_columns_are_allowed_when_rows_are_complete(self):
        report = self.summarize(
            "method\tquery_id\tevaluable\taverage_precision\tnote\n"
            "a\tq1\ttrue\t0.5\t\na\tq2\tfalse\t\tunused\n"
        )
        self.assertEqual(report["conditional_mean_by_method"], {"a": 0.5})
        self.assertEqual(report["coverage"], 0.5)

    def test_duplicate_metric_header_is_rejected_before_overwriting_scores(self):
        with self.assertRaisesRegex(ValueError, "Duplicate score column"):
            self.summarize(
                "method\tquery_id\tevaluable\taverage_precision\taverage_precision\n"
                "a\tq1\ttrue\t0.2\t0.9\nb\tq1\ttrue\t0.1\t0.8\n"
            )
        self.assertFalse(self.output.exists())

    def test_duplicate_unused_header_is_also_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate score column"):
            self.summarize(
                "method\tquery_id\tevaluable\taverage_precision\tnote\tnote\n"
                "a\tq1\ttrue\t0.2\tx\ty\n"
            )
        self.assertFalse(self.output.exists())

    def test_surplus_row_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different number of fields"):
            self.summarize(
                "method\tquery_id\tevaluable\taverage_precision\n"
                "a\tq1\ttrue\t0.2\tUNEXPECTED\n"
            )
        self.assertFalse(self.output.exists())

    def test_missing_score_field_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "different number of fields"):
            self.summarize(
                "method\tquery_id\tevaluable\taverage_precision\n"
                "a\tq1\tfalse\n"
            )
        self.assertFalse(self.output.exists())

    def test_missing_optional_column_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different number of fields"):
            self.summarize(
                "method\tquery_id\tevaluable\taverage_precision\tnote\n"
                "a\tq1\ttrue\t0.2\n"
            )
        self.assertFalse(self.output.exists())

    def test_large_unsigned_integers_cannot_silently_become_duplicate_vectors(self):
        path = self.root / "vectors.npz"
        values = np.array([[2**53, 1], [2**53 + 1, 1]], dtype=np.uint64)
        self.assertFalse(np.array_equal(values[0], values[1]))
        np.savez(path, features=values, record_ids=np.array(["a", "b"]))
        with self.assertRaisesRegex(ValueError, "precision loss"):
            c.analyze(path, "features", "record_ids", self.output, 1, None, False, False)
        self.assertFalse(self.output.exists())

    def test_large_signed_integers_are_rejected_at_both_extremes(self):
        for value in [-(2**53) - 1, 2**53 + 1]:
            with self.subTest(value=value):
                path = self.root / "vectors.npz"
                np.savez(path, features=np.array([[value, 1], [1, 0]], dtype=np.int64),
                         record_ids=np.array(["a", "b"]))
                with self.assertRaisesRegex(ValueError, "precision loss"):
                    c.load_vectors(path, "features", "record_ids")

    def test_exact_integer_boundary_values_are_preserved(self):
        path = self.root / "vectors.npz"
        original = np.array([[2**53, 1], [-(2**53), 1]], dtype=np.int64)
        np.savez(path, features=original, record_ids=np.array(["a", "b"]))
        loaded, ids, _, dtype = c.load_vectors(path, "features", "record_ids")
        np.testing.assert_array_equal(loaded.astype(np.int64), original)
        self.assertEqual(ids, ["a", "b"])
        self.assertEqual(dtype, "int64")

    def test_float32_unit_vector_analysis_is_unchanged(self):
        path = self.root / "vectors.npz"
        np.savez(path, features=np.array([[1, 0], [0, 1]], dtype=np.float32),
                 record_ids=np.array(["a", "b"]))
        report = c.analyze(path, "features", "record_ids", self.output, 1, 2, True, True)
        self.assertEqual(report["stored_dtype"], "float32")
        self.assertTrue(report["unit_norms_within_1e_5"])
        self.assertEqual(report["exact_duplicate_vector_rows"], 0)
        self.assertEqual(report["constant_dimensions"], 0)
        self.assertEqual(report["off_diagonal_cosine_mean"], 0)
        with (self.output / "summary.json").open(encoding="utf-8") as stream:
            self.assertEqual(json.load(stream)["npz_sha256"], c.digest(path))
        self.assertTrue((self.output / "analysis-complete.json").is_file())


if __name__ == "__main__":
    unittest.main()
