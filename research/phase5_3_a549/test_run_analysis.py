"""Synthetic runner integration and source/contract boundaries, with no network."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import run_analysis as runner
import public_inputs


def invented_study():
    records, values = [], []
    seqs = ["AAAAAC", "CCCCCA", "ACACAC", "CACACA"]
    for p, plate in enumerate(runner.PLATES):
        for i, well in enumerate(f"{r}{c:02d}" for r in "ABCDEFGHIJKLMNOP" for c in range(1, 25)):
            treatment = i in {0, 25, 50, 75}
            g = [0, 25, 50, 75].index(i) if treatment else 0
            gene = "SYNTH_GENE_A" if g < 2 else "SYNTH_GENE_B"
            records.append(dict(row_id=f"SYNTH_{p}_{i}", plate=plate, well=well,
                                gene=gene if treatment else "", reagent=f"SYNTH_R{g}" if treatment else "SYNTH_CTRL",
                                sequence=seqs[g] if treatment else "", condition="SYNTH_MATCHED",
                                treatment=treatment, control=not treatment,
                                pert_type="trt" if treatment else "negcon", control_type="" if treatment else "negcon",
                                negcon_control_type=""))
            vector = np.zeros(904)
            if treatment:
                vector[0 if g < 2 else 1] = 1
            values.append(vector)
    return {"metadata": pd.DataFrame(records), "features": np.asarray(values),
            "feature_names": [f"Cells_SYNTH_{i}" for i in range(904)],
            "receipt": {"cohort_origin": "SYNTHETIC_UNIT_TEST_ONLY", "selected_rows": 1536,
                        "feature_count": 904, "private_path": "/SYNTH_PRIVATE_PATH"}}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="phase53-runner-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".gitignore").write_text("outputs/\n")
        subprocess.run(["git", "-C", str(self.repo), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Synthetic", "-c",
                        "user.email=synthetic@localhost", "commit", "-qm", "Synthetic fixture"], check=True)
        self.out = self.repo / "outputs/new"
        self.study = invented_study()

    def patches(self, *, malformed=False, mutate_manifest=False):
        def fetch(out, gh=None):
            out.mkdir()
            (out / "manifest.json").write_text('{"synthetic":true}\n')
            return {}

        def load(staging):
            self.assertTrue((self.out / "frozen-analysis-contract.json").is_file())
            self.assertTrue((self.out / "input-capture-binding.json").is_file())
            contract = json.loads((self.out / "frozen-analysis-contract.json").read_text())
            self.assertTrue(contract["frozen_before_feature_loading"])
            self.assertFalse(contract["coauthor_approval_asserted"])
            if mutate_manifest:
                (staging / "manifest.json").write_text('{"tampered":true}')
            if malformed:
                return {**self.study, "features": self.study["features"][:, :2]}
            return self.study

        def report(out, summary, cross, query):
            self.assertTrue((out / "analysis-results-pending.json").is_file())
            self.assertFalse((out / "summary.json").exists())
            (out / "report.html").write_text("<html>Invented unit-test report</html>")

        return [patch.object(runner, "verify_source_pins", return_value={"files": []}),
                patch.object(public_inputs, "fetch_public_inputs", side_effect=fetch),
                patch.object(public_inputs, "load_study_inputs", side_effect=load),
                patch("report.render_report", side_effect=report)]

    def run_case(self, **kwargs):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for patcher in self.patches(**kwargs):
                stack.enter_context(patcher)
            return runner.execute(self.repo, self.out, fetch_public=True, authorize_exploratory=True)

    def test_full_parallel_pipeline_preserves_private_rows_and_frozen_contract(self):
        result = self.run_case()
        self.assertEqual(result["status"], "COMPLETE_EXPLORATORY")
        self.assertAlmostEqual(result["crossguide"]["masks"]["different_row_and_column"]["contrast"], 1.0)
        self.assertEqual(result["query_information"]["input_accounting"]["treatment_unique_reagent_count"], 4)
        public = (self.out / "summary.json").read_text()
        for forbidden in ["SYNTH_GENE_A", "AAAAAC", "/SYNTH_PRIVATE_PATH", "SYNTH_R0"]:
            self.assertNotIn(forbidden, public)
        self.assertTrue(list((self.out / "PRIVATE").glob("*.csv")))
        for line in (self.out / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)

    def test_authorization_and_clean_source_are_checked_before_inputs(self):
        with self.assertRaisesRegex(ValueError, "authorize"):
            runner.execute(self.repo, self.out, fetch_public=True)
        (self.repo / "untracked.txt").write_text("Uncommitted source")
        with self.assertRaisesRegex(ValueError, "Commit"):
            runner.execute(self.repo, self.out, fetch_public=True, authorize_exploratory=True)
        self.assertFalse(self.out.exists())

    def test_unexpected_schema_blocks_before_scoring(self):
        with self.assertRaisesRegex(RuntimeError, "input preparation"):
            self.run_case(malformed=True)
        result = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["scientific_results_computed"])
        self.assertFalse((self.out / "PRIVATE").exists())

    def test_report_failure_does_not_claim_completion(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for patcher in self.patches()[:3]:
                stack.enter_context(patcher)
            stack.enter_context(patch("report.render_report", side_effect=OSError("Synthetic rendering failure")))
            with self.assertRaises(OSError):
                runner.execute(self.repo, self.out, fetch_public=True, authorize_exploratory=True)
        self.assertFalse((self.out / "summary.json").exists())
        self.assertFalse((self.out / "SHA256SUMS").exists())
        status = json.loads((self.out / "RUN_STATUS.json").read_text())
        self.assertEqual(status["status"], "ANALYSES_FINISHED_REPORT_PENDING")
        self.assertTrue((self.out / "analysis-results-pending.json").is_file())

    def test_manifest_change_is_not_accepted_as_the_frozen_capture(self):
        with self.assertRaisesRegex(RuntimeError, "input preparation"):
            self.run_case(mutate_manifest=True)
        self.assertEqual(json.loads((self.out / "summary.json").read_text())["status"], "BLOCKED")

    def test_independent_query_audit_survives_scoring_failure_without_fake_effect(self):
        with patch("crossguide.analyze_crossguide", side_effect=ValueError("SYNTH_SECRET_IDENTIFIER")):
            result = self.run_case()
        self.assertEqual(result["status"], "PARTIAL_EXPLORATORY")
        self.assertIsNone(result["crossguide"])
        self.assertIsNotNone(result["query_information"])
        self.assertNotIn("SYNTH_SECRET_IDENTIFIER", json.dumps(result))

    def test_output_guard_rejects_existing_outside_and_unignored_destinations(self):
        with self.assertRaises(ValueError):
            runner.guarded_output(self.repo, self.repo.parent / "outside")
        self.out.mkdir(parents=True)
        with self.assertRaises(ValueError):
            runner.guarded_output(self.repo, self.out)
        (self.repo / ".gitignore").write_text("")
        with self.assertRaises(ValueError):
            runner.guarded_output(self.repo, self.repo / "outputs/new2")

    def test_mac_style_ancestor_alias_runs_and_returns_canonical_output(self):
        alias = Path(self.temp.name).resolve() / "var-alias"
        alias.symlink_to(Path(self.temp.name).resolve(), target_is_directory=True)
        self.out = alias / "repo/outputs/mac-alias-run"
        result = self.run_case()
        self.assertEqual(result["status"], "COMPLETE_EXPLORATORY")
        self.assertTrue((self.out.resolve() / "summary.json").is_file())
        self.assertAlmostEqual(result["crossguide"]["masks"]["different_row_and_column"]["contrast"], 1.0)
        repo, out = runner.guarded_output(self.repo, alias / "repo/outputs/another-new")
        self.assertEqual(repo, self.repo.resolve())
        self.assertEqual(out, self.repo.resolve() / "outputs/another-new")

    def test_output_symlinks_within_checkout_remain_rejected(self):
        outputs = self.repo / "outputs"
        outputs.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        inside = self.repo / "other-directory"
        inside.mkdir()
        for name, target in [("escape", outside), ("internal", inside), ("back-to-repo", self.repo)]:
            with self.subTest(name=name):
                link = outputs / name
                link.symlink_to(target.resolve(), target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "symlinks"):
                    runner.guarded_output(self.repo, link / "fresh")
                self.assertFalse((target / "fresh").exists())
        leaf = outputs / "dangling"
        leaf.symlink_to(outside / "missing", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "fresh"):
            runner.guarded_output(self.repo, leaf)

    def test_output_parent_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "parent traversal"):
            runner.guarded_output(self.repo, self.repo / "outputs/../outputs/traversal")
        self.assertFalse((self.repo / "outputs/traversal").exists())

    def test_protocol_cannot_be_relabelled_as_validated_or_widened(self):
        protocol = json.loads((runner.SCRIPT_DIR / "PROTOCOL.json").read_text())
        runner.validate_protocol(protocol)
        for patch_value in [{"status": "BIOLOGICALLY_VALIDATED"}, {"plates": ["OTHER"]},
                            {"expected_capture": {"rows": 1536, "features": 10, "physical_plates": 4}},
                            {"schema_version": "phase53.authorized_exploratory.v1"},
                            {"plates": ["BR00116996", "BR00116997", "BR00116998", "BR00116999"]},
                            {"expected_conditions": {"Cell_type": "U2OS"}},
                            {"excluded_condition_plates": []}]:
            with self.subTest(value=patch_value), self.assertRaises(ValueError):
                runner.validate_protocol({**protocol, **patch_value})


if __name__ == "__main__":
    unittest.main()
