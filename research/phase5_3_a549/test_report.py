"""Synthetic result-contract checks; no source data, model or network required."""

from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from report import FILES, MASKS, PRIMARY, SECONDARY, _availability, _availability_html, render_report


class MetricCells(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.cells = {}
        self.active = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.active = dict(attrs).get("data-metric")

    def handle_data(self, data):
        if self.active:
            self.cells[self.active] = self.cells.get(self.active, "") + data

    def handle_endtag(self, tag):
        if tag == "td":
            self.active = None


def synthetic_results(*, empty=False):
    plates = ["SYNTH_PRIVATE_PLATE_A", "SYNTH_PRIVATE_PLATE_B", "SYNTH_PRIVATE_PLATE_C", "SYNTH_PRIVATE_PLATE_D"]
    masks, genes, observations = {}, [], []
    for mask in MASKS:
        pairs = [{"plate_a": a, "plate_b": b, "contrast": None if empty else 0.314159,
                  "position_contrast": None if empty else 0.0123, "weight": 0.0 if empty else 1 / 6}
                 for a, b in combinations(plates, 2)]
        masks[mask] = {"contrast": None if empty else 0.234567,
                       "position_contrast": None if empty else 0.0123,
                       "eligible_gene_groups": 0 if empty else 2,
                       "complete_guide_pairs": 0 if empty else 2,
                       "eligible_observations": 0 if empty else 48,
                       "unordered_plate_pairs": pairs}
        if not empty:
            for index in range(2):
                genes.append({"mask": mask, "gene": f"SYNTH_PRIVATE_SOURCE_GENE_{index}",
                              "contrast": 0.10 + index * 0.03, "position_contrast": 0.02 + index * 0.01,
                              "complete_pair_eligible": True, "weight": 0.5})
            genes.append({"mask": mask, "gene": "SYNTH_PRIVATE_EXCLUDED_GENE", "contrast": 99999.0,
                          "position_contrast": 99999.0, "complete_pair_eligible": False, "weight": 0.0})
    if not empty:
        # The first anchor appears twice and must count once.  The second has
        # raw support but zero canonical weight and must not count as complete.
        for _ in range(2):
            observations.append({"mask": PRIMARY, "anchor_plate": plates[0],
                                 "row_id": "SYNTH_PRIVATE_ROW_A", "gene": "SYNTH_PRIVATE_SOURCE_GENE_0",
                                 "guide": "SYNTH_PRIVATE_GUIDE_HASH", "weight": 0.125,
                                 "complete_pair_eligible": True})
        observations.append({"mask": PRIMARY, "anchor_plate": plates[0],
                             "row_id": "SYNTH_PRIVATE_RAW_SUPPORTED_ROW", "gene": "SYNTH_PRIVATE_EXCLUDED_GENE",
                             "guide": "SYNTH_PRIVATE_GUIDE_HASH", "weight": 0.0,
                             "complete_pair_eligible": False})
        observations.append({"mask": SECONDARY, "anchor_plate": plates[1],
                             "row_id": "SYNTH_PRIVATE_SECONDARY_ROW", "gene": "SYNTH_PRIVATE_SOURCE_GENE_0",
                             "guide": "SYNTH_PRIVATE_GUIDE_HASH", "weight": 0.125,
                             "complete_pair_eligible": True})
    cross = {"summary": {"masks": masks, "initial_noncontrol_anchors_per_plate": {plate: 2 for plate in plates},
                          "paired_mask_difference": {"contrast_difference": None if empty else 0.00123,
                                                     "intersection_gene_groups": 0 if empty else 2,
                                                     "intersection_genes_with_changed_complete_guide_pairs": 0}},
             "private_genes": pd.DataFrame(genes, columns=["mask", "gene", "contrast", "position_contrast", "complete_pair_eligible", "weight"]),
             "private_observations": pd.DataFrame(observations, columns=["mask", "anchor_plate", "row_id", "gene", "guide", "weight", "complete_pair_eligible"]),
             "private_anchors": pd.DataFrame([{"gene": "SYNTH_PRIVATE_EXCLUDED_GENE", "has_positive_and_reference": True}] * 99)}
    query = {"summary": {"descriptions": {
        key: {"distinct_signature_count": 8, "unique_signature_reagent_count": 7,
              "analyzed_unique_reagent_count": 11, "excluded_conflicting_unique_reagent_count": 2,
              "conditional_identity_entropy_bits": 1.25,
              "tie_only_expected_exact_identity_hit_at_1": 8 / 11}
        for key in ("category_only", "gene_aware")}},
        "private_collision_ledger": pd.DataFrame([{"reagent": "SYNTH_PRIVATE_REAGENT", "sequence": "SYNTH_PRIVATE_SEQUENCE"}])}
    return cross, query


def synthetic_availability():
    """Invented profile absence only; no real cohort or mechanism claim."""
    plates = ["SYNTH_PRIVATE_PLATE_A", "SYNTH_PRIVATE_PLATE_B", "SYNTH_PRIVATE_PLATE_C", "SYNTH_PRIVATE_PLATE_D"]
    counts = [379, 375, 380, 336]
    return {
        "planned_physical_wells": 1536,
        "observed_profile_rows": 1470,
        "absent_profile_wells": 66,
        "by_plate": {plate: {"planned_physical_wells": 384, "observed_profile_rows": count,
                              "absent_profile_wells": 384 - count} for plate, count in zip(plates, counts)},
        "planned_role_counts": {"treatment": 12, "control": 1524, "unclassified": 0},
        "observed_role_counts": {"treatment": 8, "control": 1462, "unclassified": 0},
        "absent_role_counts": {"treatment": 4, "control": 62},
        "planned_control_class_counts": {"negcon": 1486, "SYNTH_PRIVATE_CONTROL_LABEL": 38},
        "observed_control_class_counts": {"negcon": 1424, "SYNTH_PRIVATE_CONTROL_LABEL": 38},
        "absent_control_class_counts": {"negcon": 62},
        "representation_counts": {
            "treatment_source_gene_strings": {"planned_distinct": 3, "observed_distinct": 2,
                "absent_well_distinct": 1, "entirely_absent_distinct": 1},
            "SYNTH_PRIVATE_UNREQUESTED_FIELD": {"planned_distinct": 99999},
        },
        "private_rows": ["SYNTH_PRIVATE_SOURCE_IDENTIFIER"],
        "missingness_interpretation": "SYNTH_PRIVATE_UNTRUSTED_TEXT",
    }


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temporary.name)
        cls.summary = {"status": "COMPLETE_EXPLORATORY", "source_commit": "a" * 40,
                       "profile_availability": synthetic_availability()}
        cls.cross, cls.query = synthetic_results()
        render_report(cls.out, cls.summary, cls.cross, cls.query)
        cls.html = (cls.out / "report.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_scientific_assets_and_relative_local_links_are_created(self):
        self.assertEqual(len(list((self.out / "figures").glob("*.png"))), 5)
        for name in FILES:
            content = (self.out / "figures" / name).read_bytes()
            self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(len(content), 1000)
            self.assertIn(f'src="figures/{name}"', self.html)
        self.assertTrue((self.out / "report.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertIn('href="report.pdf"', self.html)
        self.assertNotIn(str(self.out), self.html)

    def test_public_report_does_not_embed_source_identifiers_or_private_tables(self):
        self.assertNotIn("SYNTH_PRIVATE", self.html)
        self.assertNotIn("99999", self.html)
        self.assertNotIn("private_collision_ledger", self.html)
        self.assertNotIn("private_observations", self.html)
        self.assertIn("COMPLETE_EXPLORATORY", self.html)
        self.assertIn("a" * 40, self.html)
        self.assertIn("not six independent experiments", self.html)
        self.assertIn("different scales", self.html)

    def test_displayed_numbers_and_complete_coverage_follow_result_contract(self):
        cells = MetricCells(self.html).cells
        self.assertEqual(cells["query-category_only-distinct_signature_count"], "8")
        self.assertEqual(cells["query-category_only-unique_signature_reagent_count"], "7")
        self.assertEqual(cells["query-category_only-analyzed_unique_reagent_count"], "11")
        self.assertEqual(cells["query-category_only-conditional_identity_entropy_bits"], "1.25")
        self.assertEqual(cells["coverage-P1-initial"], "2")
        self.assertEqual(cells["coverage-P1-complete"], "1")
        self.assertEqual(cells["coverage-P2-complete"], "0")
        self.assertIn("0.314159", self.html)
        self.assertIn("0.234567", self.html)
        self.assertIn("0.00123", self.html)

    def test_observed_and_design_denominators_remain_separate_and_anonymous(self):
        cells = MetricCells(self.html).cells
        self.assertEqual(cells["availability-total-planned"], "1536")
        self.assertEqual(cells["availability-total-observed"], "1470")
        self.assertEqual(cells["availability-total-absent"], "66")
        self.assertEqual(cells["availability-P4-absent"], "48")
        self.assertEqual(cells["availability-control-absent"], "62")
        self.assertEqual(cells["coverage-P1-initial"], "2")
        self.assertEqual(cells["coverage-P1-complete"], "1")
        self.assertEqual(cells["representation-treatment_source_gene_strings-entirely_absent_distinct"], "1")
        self.assertIn("Entirely absent units remain in the source-design denominator", self.html)
        self.assertIn("conditional on the observed subset", self.html)
        self.assertIn("Absence has an unknown cause", self.html)
        self.assertIn("observed treatment profiles", self.html)
        self.assertIn("Other or unresolved source control classes", self.html)
        self.assertNotIn("SYNTH_PRIVATE", self.html)

    def test_inconsistent_availability_never_appears_as_verified_counts(self):
        availability = synthetic_availability()
        availability["observed_profile_rows"] = 1536
        section = _availability_html(_availability({"profile_availability": availability}))
        self.assertIn("unavailable", section)
        self.assertIn("Unavailable", section)
        self.assertNotIn("1536", section)
        self.assertNotIn("1470", section)
        self.assertNotIn("SYNTH_PRIVATE", section)

    def test_zero_eligible_and_missing_analysis_panels_are_graceful(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            cross, _ = synthetic_results(empty=True)
            render_report(out, {"status": "PARTIAL_EXPLORATORY", "source_commit": "b" * 40}, cross, None)
            text = (out / "report.html").read_text(encoding="utf-8")
            self.assertIn("Unavailable", text)
            self.assertIn("PARTIAL_EXPLORATORY", text)
            cells = MetricCells(text).cells
            self.assertEqual(cells["coverage-P1-complete"], "0")
            self.assertEqual(len(list((out / "figures").glob("*.png"))), 5)
            self.assertTrue((out / "report.pdf").read_bytes().startswith(b"%PDF-"))
            self.assertNotIn(">nan<", text.lower())
            # The engine allows a secondary-only result.  Its absent primary
            # analysis must remain unavailable rather than turn into zeros.
            del cross["summary"]["masks"][PRIMARY]
            render_report(out, {"status": "PARTIAL_EXPLORATORY", "source_commit": "b" * 40}, cross, None)
            cells = MetricCells((out / "report.html").read_text(encoding="utf-8")).cells
            self.assertNotIn("coverage-P1-complete", cells)
        with self.assertRaisesRegex(ValueError, "already exist"):
            render_report(self.out / "does-not-exist", {}, None, None)


if __name__ == "__main__":
    unittest.main()
