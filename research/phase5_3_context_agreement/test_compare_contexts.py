"""Invented completed-result tables only; no profiles, network or real identities."""
import csv
import io
from itertools import permutations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import compare_contexts as app


def csv_bytes(columns, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def write_manifest(out):
    names = ("summary.json", app.GENES, app.OBSERVATIONS, app.CONTRACT)
    (out / "SHA256SUMS").write_text("".join(app.common.digest((out / n).read_bytes()) + "  " + n + "\n" for n in names))


def fixture(folder, context, *, rename=False, changed_pair=False):
    repo = folder / "repo"
    out = repo / ("outputs/phase53-a549-rowfix-v2/analysis.synthetic" if context == "a549" else "outputs/original")
    (out / "PRIVATE").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("outputs/\n")
    plates = [f"SYNTH_{context}_P{i}" for i in range(4)]
    gene_names = ["SYNTH_ALPHA_NEW" if rename else "SYNTH_ALPHA", "SYNTH_BETA"]
    primary = [.2, -.1] if context == "u2os" else [.1, .05]
    rows, obs, mask_summaries = [], [], {}
    for mask_index, mask in enumerate(app.common.MASKS):
        effects = [x / (mask_index + 1) for x in primary]
        for index, (gene, value) in enumerate(zip(gene_names, effects)):
            row = {key: "0" for key in app.common.COLUMNS}
            row.update(mask=mask, gene=gene, source_gene_status="usable_recorded_source_gene_string_only",
                       initial_anchor_wells="8", initial_sequence_guides="2", initial_plates="4",
                       finite_anchor_wells="8", label_usable_anchor_wells="8", complete_guide_pairs="1",
                       contrast=str(value), position_contrast=str(value / 2), complete_pair_eligible="True", weight="0.5")
            rows.append(row)
            guide_names = ["seq_sha256:" + app.common.digest((str(index) + str(g)).encode()) for g in range(2)]
            if changed_pair and index == 1:
                guide_names[1] = "seq_sha256:" + app.common.digest(b"SYNTH_DIFFERENT_GUIDE")
            for p, q in permutations(plates, 2):
                for direction, guide in enumerate(guide_names):
                    well = ("A01", "B02", "C03", "D04")[index * 2 + direction]
                    obs.append(dict(mask=mask, row_id=p + "_" + well, gene=gene,
                                    guide=guide, partner_guide=guide_names[1-direction],
                                    anchor_plate=p, gallery_plate=q, well=well,
                                    positive_mean_cosine=.4 + value, reference_mean_cosine=.4,
                                    contrast=value, position_positive_mean=.5 + value / 2,
                                    position_reference_mean=.5, position_contrast=value / 2,
                                    positive_wells=1, reference_wells=1, reference_guides=1,
                                    reference_genes=1, weight=1/48, complete_pair_eligible=True))
        mean = sum(effects) / 2
        pairs = [{"plate_a": plates[i], "plate_b": plates[j], "weight": 1/6, "contrast": mean}
                 for i in range(4) for j in range(i+1, 4)]
        mask_summaries[mask] = {"eligible_gene_groups": 2, "complete_guide_pairs": 2,
                                "contrast": mean, "position_contrast": mean/2,
                                "eligible_observations": 48, "unordered_plate_pairs": pairs}
    contract = {"source_commit": app.PINS[context]["source"],
                "study_python_sha256": {"crossguide.py": app.ENGINE_SHA, "query_audit.py": app.QUERY_SHA}}
    (out / app.CONTRACT).write_text(json.dumps(contract))
    summary = {"status": "COMPLETE_EXPLORATORY", "source_commit": app.PINS[context]["source"],
               "analysis_contract_sha256": app.common.digest((out / app.CONTRACT).read_bytes()),
               "errors": {}, "historical_results_modified": False,
               "input_receipt": {"feature_count": 904, "feature_schema_sha256": app.FEATURE_SCHEMA,
                                 "upstream_normalization_scope": "source_batch_global", "plates": plates},
               "crossguide": {"initial_source_gene_groups_including_missing_value": 2,
                              "initial_noncontrol_anchors": 16,
                              "source_gene_group_status_counts": {"usable_recorded_source_gene_string_only": 2},
                              "masks": mask_summaries,
                              "paired_mask_difference": {"intersection_gene_groups": 2, "primary_only_gene_groups": 0,
                                                         "secondary_only_gene_groups": 0,
                                                         "contrast_difference": -sum(primary)/4}}}
    (out / "summary.json").write_text(json.dumps(summary))
    (out / app.GENES).write_bytes(csv_bytes(app.common.COLUMNS, rows))
    (out / app.OBSERVATIONS).write_bytes(csv_bytes(app.OBS_COLUMNS, obs))
    write_manifest(out)
    (folder / "status-receipt.json").write_text(json.dumps({"status": "EXPLORATORY_ANALYSIS_COMPLETE",
                                                           "commit": app.PINS[context]["source"], "output": str(out)}))
    if context == "a549":
        (out.parent / "status-receipt.json").write_text(json.dumps({"status": "EXPLORATORY_ANALYSIS_COMPLETE",
                                                                   "commit": app.PINS[context]["source"], "completed_output": str(out)}))
    return repo, out


class ContextAgreementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.u_repo, self.u = fixture(self.root / "u work", "u2os")
        self.a_repo, self.a = fixture(self.root / "a work", "a549")
        self.pin_results()

    def pin_results(self):
        pins = {name: dict(app.PINS[name], summary=app.common.digest((out / "summary.json").read_bytes()))
                for name, out in (("u2os", self.u), ("a549", self.a))}
        self.addCleanup(patch.stopall)
        patch.object(app, "PINS", pins).start()

    def test_complete_diagnostic_matches_pairs_is_aggregate_and_preserves_all_inputs(self):
        original = {p: p.read_bytes() for out in (self.u, self.a) for p in out.rglob("*") if p.is_file()}
        output, diagnostic = app.compare(self.u, self.a)
        values = diagnostic["matched_context_comparison"][app.common.MASKS[0]]
        self.assertEqual(values["identical_complete_guide_pair_sets"], 2)
        self.assertAlmostEqual(values["a549_minus_u2os_matched_distribution"]["mean"], .025)
        self.assertEqual(values["sign_counts_u2os_then_a549"]["positive_positive"], 1)
        self.assertEqual(values["sign_counts_u2os_then_a549"]["negative_positive"], 1)
        self.assertAlmostEqual(values["spearman_descriptive_average_exact_tie_ranks"], 1)
        text = (output / "context-agreement-summary.json").read_text()
        for forbidden in ("SYNTH_ALPHA", "SYNTH_BETA", "seq_sha256:", str(self.root)):
            self.assertNotIn(forbidden, text)
        self.assertEqual(output.parent, self.a.parent)
        for path, value in original.items(): self.assertEqual(path.read_bytes(), value)
        self.assertFalse(diagnostic["profiles_read"])
        self.assertFalse(diagnostic["github_publication_verified"])

    def test_same_counts_different_genes_do_not_establish_same_population(self):
        _, self.a = fixture(self.root / "renamed", "a549", rename=True)
        self.pin_results()
        _, diagnostic = app.compare(self.u, self.a)
        values = diagnostic["matched_context_comparison"][app.common.MASKS[0]]
        self.assertEqual(values["shared_literal_gene_groups"], 1)
        self.assertEqual(values["identical_complete_guide_pair_sets"], 1)
        self.assertIsNone(values["pearson_descriptive"])

    def test_same_gene_changed_guide_pair_is_held(self):
        _, self.a = fixture(self.root / "different guide", "a549", changed_pair=True)
        self.pin_results()
        _, diagnostic = app.compare(self.u, self.a)
        values = diagnostic["matched_context_comparison"][app.common.MASKS[0]]
        self.assertEqual(values["shared_literal_gene_groups"], 2)
        self.assertEqual(values["shared_gene_groups_held_for_different_guide_pair_sets"], 1)
        self.assertEqual(values["identical_complete_guide_pair_sets"], 1)

    def test_tampered_csv_and_changed_summary_pin_fail(self):
        path = self.a / app.OBSERVATIONS
        path.write_bytes(path.read_bytes() + b"tampered\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            app.compare(self.u, self.a)
        write_manifest(self.a)
        with self.assertRaises(ValueError): app.compare(self.u, self.a)
        summary = self.u / "summary.json"
        summary.write_text(summary.read_text() + "\n")
        write_manifest(self.u)
        with self.assertRaisesRegex(ValueError, "exact uploaded"):
            app.compare(self.u, self.a)

    def test_duplicate_and_nonfinite_observations_fail_even_with_updated_manifest(self):
        original = (self.a / app.OBSERVATIONS).read_bytes()
        cases = [original + original.splitlines(keepends=True)[1],
                 original.replace(b",0.1,", b",nan,", 1)]
        for payload in cases:
            with self.subTest(payload=payload[-30:]):
                (self.a / app.OBSERVATIONS).write_bytes(payload); write_manifest(self.a)
                with self.assertRaises(ValueError): app.compare(self.u, self.a)

    def test_observation_aggregate_and_missing_direction_fail(self):
        original = (self.a / app.OBSERVATIONS).read_bytes()
        reader = csv.DictReader(io.StringIO(original.decode()))
        rows = list(reader)
        for payload in (csv_bytes(app.OBS_COLUMNS, rows[1:]),
                        csv_bytes(app.OBS_COLUMNS, [dict(r, weight=.04) if i == 0 else r for i, r in enumerate(rows)])):
            (self.a / app.OBSERVATIONS).write_bytes(payload); write_manifest(self.a)
            with self.assertRaises(ValueError): app.compare(self.u, self.a)

    def test_frozen_engine_binding_fails(self):
        contract = json.loads((self.a / app.CONTRACT).read_text())
        contract["study_python_sha256"]["crossguide.py"] = "0" * 64
        (self.a / app.CONTRACT).write_text(json.dumps(contract)); write_manifest(self.a)
        with self.assertRaisesRegex(ValueError, "Frozen"):
            app.compare(self.u, self.a)

    def test_reordering_result_rows_preserves_scientific_diagnostic(self):
        _, before = app.compare(self.u, self.a)
        for relative in (app.GENES, app.OBSERVATIONS):
            lines = (self.a / relative).read_bytes().splitlines(keepends=True)
            (self.a / relative).write_bytes(lines[0] + b"".join(reversed(lines[1:])))
        write_manifest(self.a)
        _, after = app.compare(self.u, self.a)
        self.assertEqual(before["matched_context_comparison"], after["matched_context_comparison"])

    def test_rank_ties_zero_variance_and_small_populations(self):
        self.assertEqual(app.ranks([10, 20, 20, 40]), [1, 2.5, 2.5, 4])
        self.assertAlmostEqual(app.correlation(app.ranks([10, 20, 20, 40]), app.ranks([4, 3, 3, 1])), -1)
        self.assertIsNone(app.correlation([1, 1], [2, 3]))
        self.assertIsNone(app.correlation([], []))
        self.assertIsNone(app.correlation([1], [2]))

    def test_mac_ancestor_alias_is_allowed_but_internal_symlink_and_traversal_fail(self):
        alias = self.root / "var-alias"; alias.symlink_to(self.root, target_is_directory=True)
        _, value = app.compare(alias / "u work/repo/outputs/original", self.a)
        self.assertTrue(value["ordered_904_feature_schema_identical"])
        path = self.a / app.OBSERVATIONS
        data = path.read_bytes(); path.unlink()
        other = self.root / "outside.csv"; other.write_bytes(data); path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"): app.compare(self.u, self.a)
        with self.assertRaises(ValueError): app.location(self.u / "../original")

    def test_bounded_receipt_discovery_handles_actual_nested_a549_structure(self):
        downloads = self.root / "Downloads"; downloads.mkdir()
        _, self.u = fixture(downloads / "perturb-lm-phase53.SYNTHETIC", "u2os")
        _, self.a = fixture(downloads / "perturb-lm-phase53-a549.SYNTHETIC", "a549")
        self.pin_results()
        with patch.object(app.common, "EXPECTED_SUMMARY_SHA256", app.PINS["u2os"]["summary"]):
            u, a = app.discover(downloads)
        self.assertEqual(u, self.u)
        self.assertEqual(a, self.a)


if __name__ == "__main__":
    unittest.main()
