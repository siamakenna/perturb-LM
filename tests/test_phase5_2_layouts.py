"""Synthetic layout design tests; no actual cohort, acquisition or model is evaluated."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from perturb_lm.audits.layouts import compare_compound_layouts, read_tsv, sha256

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/phase5_2"
SCRIPT = ROOT / "scripts/audit_phase5_2_layouts.py"
ROLES = ("target1_metadata", "target1_platemap", "target2_metadata", "target2_platemap")


def load_script():
    spec = importlib.util.spec_from_file_location("phase52_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompoundLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tables = [read_tsv(FIXTURES / f"{role}.tsv") for role in ROLES]

    def run_audit(self):
        return compare_compound_layouts(*self.tables)

    def test_layout_overlap_separates_coordinates_samples_and_measurements(self):
        summary, keys, _, _ = self.run_audit()
        self.assertEqual(summary["shared_standardized_key_groups"], 3)
        self.assertEqual(summary["shared_groups_with_any_different_coordinate_pair"], 2)
        self.assertEqual(summary["shared_groups_with_only_same_coordinate_pairs"], 1)
        self.assertEqual(summary["cross_layout_different_coordinate_pairs"], 3)
        self.assertEqual(summary["shared_groups_with_any_identical_source_sample_identifier"], 1)
        self.assertFalse(summary["execution_allowed"])
        self.assertEqual(summary["status"], "PROPOSED_NOT_APPROVED")
        for field in (
            "measured_physical_plates",
            "independent_cultures",
            "independent_batches",
            "matched_dose_duration_cell_context_pairs",
            "biological_positive_pairs",
        ):
            self.assertIsNone(summary[field])
        group = next(row for row in keys if row["InChIKey"].startswith("A"))
        self.assertEqual(group["target1_sample_ids"], ["SYNTH_A1", "SYNTH_A1_OTHER"])
        self.assertEqual(group["target2_sample_ids"], ["SYNTH_A2"])
        self.assertTrue(group["multiple_sample_ids_within_a_layout"])
        self.assertEqual(group["shared_source_sample_identifiers"], [])

    def test_identical_annotation_duplicates_are_counted_without_fanout(self):
        summary, keys, _, annotations = self.run_audit()
        self.assertEqual(summary["layouts"]["Target2"]["annotation_rows"], 6)
        self.assertEqual(
            summary["layouts"]["Target2"]["identical_duplicate_annotation_rows_collapsed"], 1
        )
        self.assertEqual(
            sum(r["status"] == "identical_duplicate_collapsed" for r in annotations), 1
        )
        group = next(row for row in keys if row["InChIKey"].startswith("A"))
        self.assertEqual(group["cross_layout_coordinate_pairs"], 2)

    def test_partial_maps_report_coverage_without_implying_complete_layouts(self):
        summary, _, _, _ = self.run_audit()
        for name, count in (("Target1", 10), ("Target2", 5)):
            with self.subTest(layout=name):
                self.assertFalse(summary["layouts"][name]["map_complete_384_wells"])
                self.assertEqual(
                    summary["layouts"][name]["missing_384_well_coordinates"], 384 - count
                )

    def test_reserved_annotation_columns_cannot_replace_audit_status(self):
        self.tables[0][0]["status"] = "pretend_approved"
        with self.assertRaisesRegex(ValueError, "reserved audit ledger"):
            self.run_audit()

    def test_conflicting_duplicate_annotations_fail_closed(self):
        for field, value in (
            ("InChIKey", "XXXXXXXXXXXXXXXX-YYYYYYYYYY-Z"),
            ("pert_type", "control"),
            ("target_list", "SYNTH_DIFFERENT_TARGET"),
        ):
            with self.subTest(field=field):
                tables = copy.deepcopy(self.tables)
                tables[2][1][field] = value
                with self.assertRaisesRegex(ValueError, "conflicting annotations"):
                    compare_compound_layouts(*tables)

    def test_cross_layout_sample_identity_contradictions_fail_closed(self):
        self.tables[2][3]["InChIKey"] = "ZZZZZZZZZZZZZZ-YYYYYYYYYY-X"
        with self.assertRaisesRegex(ValueError, "cross-layout identity"):
            self.run_audit()

    def test_full_key_required_not_connectivity_block_or_gene_name(self):
        summary, keys, _, _ = self.run_audit()
        shared = [row for row in keys if row["present_in_both_layouts"]]
        self.assertFalse(any(row["InChIKey"].startswith("GGGG") for row in shared))
        self.assertEqual(summary["union_standardized_key_groups"], 5)
        # SYNTH_D1 and SYNTH_E2 share a first key block and target label, but not a full key.
        self.assertEqual(sum(row["InChIKey"].startswith("GGGG") for row in keys), 2)
        self.assertTrue(
            all(
                row["identity_status"] == "unmatched_standardized_key"
                for row in keys
                if not row["present_in_both_layouts"]
            )
        )

    def test_controls_missing_unknown_and_invalid_keys_retained_in_ledger(self):
        summary, _, wells, _ = self.run_audit()
        reasons = summary["layouts"]["Target1"]["exclusion_reason_counts_nonexclusive"]
        for reason in (
            "control",
            "missing_map_sample_identifier",
            "unmatched_sample_identifier",
            "unknown_treatment_control_status",
            "invalid_full_inchikey",
        ):
            self.assertEqual(reasons[reason], 1)
        self.assertEqual(summary["layouts"]["Target1"]["excluded_layout_wells"], 5)
        missing = next(r for r in wells if r["layout"] == "Target1" and r["well_position"] == "F01")
        self.assertEqual(missing["exclusion_reasons"], "missing_map_sample_identifier")
        # DMSO solvent does not make a missing-ID well a known control.
        self.assertNotIn("control", missing["exclusion_reasons"])

    def test_missing_key_and_annotation_sample_have_explicit_accounting(self):
        self.tables[0][0]["InChIKey"] = "NA"
        self.tables[0].append({key: "" for key in self.tables[0][0]})
        summary, _, _, annotations = self.run_audit()
        self.assertEqual(
            summary["layouts"]["Target1"]["exclusion_reason_counts_nonexclusive"][
                "missing_full_inchikey"
            ],
            1,
        )
        self.assertEqual(sum(r["status"] == "missing_sample_identifier" for r in annotations), 1)

    def test_conflicting_control_labels_fail_closed(self):
        self.tables[0][0]["control_type"] = "negcon"
        with self.assertRaisesRegex(ValueError, "contradictory treatment/control"):
            self.run_audit()

    def test_canonical_well_aliases_do_not_create_extra_positions(self):
        self.tables[1][0]["well_position"] = "a1"
        summary, keys, _, _ = self.run_audit()
        self.assertEqual(summary["shared_standardized_key_groups"], 3)
        self.assertIn("A01", keys[0]["target1_coordinates"])
        self.tables[1].append(dict(self.tables[1][0], well_position="A01"))
        with self.assertRaisesRegex(ValueError, "duplicate canonical well"):
            self.run_audit()

    def test_invalid_well_and_numeric_identifier_coercion_fail_closed(self):
        self.tables[1][0]["well_position"] = "Q25"
        with self.assertRaisesRegex(ValueError, "384-well"):
            self.run_audit()
        self.tables[1][0]["well_position"] = "A01"
        self.tables[0][0]["broad_sample"] = 123
        with self.assertRaisesRegex(ValueError, "remain strings"):
            self.run_audit()

    def test_input_reordering_preserves_aggregate_and_key_results(self):
        before, keys_before, _, _ = self.run_audit()
        self.tables = [list(reversed(table)) for table in self.tables]
        after, keys_after, _, _ = self.run_audit()
        self.assertEqual(before, after)
        self.assertEqual(keys_before, keys_after)

    def test_tsv_rejects_duplicate_columns_and_ragged_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.tsv"
            for text in ("a\ta\n1\t2\n", "a\tb\n1\n", "a\tb\n1\t2\t3\n"):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    read_tsv(path)


class LayoutCliTests(unittest.TestCase):
    def test_output_guards_reject_existing_outside_and_symlink_paths(self):
        helper = load_script()
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / ".gitignore").write_text("/outputs/\n")
            outside = Path(temp) / "external"
            outside.mkdir()
            with self.assertRaises(ValueError):
                helper.guarded_output(outside / "new", repo)
            (repo / "outputs").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                helper.guarded_output(repo / "outputs/new", repo)
            (repo / "outputs").unlink()
            existing = repo / "outputs/existing"
            existing.mkdir(parents=True)
            with self.assertRaises(ValueError):
                helper.guarded_output(existing, repo)
            self.assertEqual(
                helper.guarded_output(repo / "outputs/new", repo),
                (repo / "outputs/new").resolve(),
            )

    def test_output_guard_canonicalizes_symlinked_repository_ancestor(self):
        helper = load_script()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            physical = root / "physical"
            physical.mkdir()
            alias = root / "alias"
            alias.symlink_to(physical, target_is_directory=True)
            repo = alias / "repo"
            repo.mkdir()
            (repo / ".gitignore").write_text("/outputs/\n")
            self.assertEqual(
                helper.guarded_output(repo / "outputs/new", repo),
                physical / "repo/outputs/new",
            )

    def test_provenance_hash_role_revision_and_path_failures(self):
        helper = load_script()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            revision = "a" * 40
            manifest = {"schema_version": 1, "repository": "jump-cellpainting/JUMP-Target"}
            manifest.update(revision=revision, files={})
            for role in ROLES:
                path = root / f"{role}.tsv"
                shutil.copyfile(FIXTURES / path.name, path)
                manifest["files"][role] = {
                    "path": path.name,
                    "sha256": sha256(path),
                    "url": (
                        "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/"
                        f"{revision}/{helper.SOURCE_FILENAMES[role]}"
                    ),
                }
            provenance = root / "provenance.json"
            provenance.write_text(json.dumps(manifest))
            args = SimpleNamespace(
                synthetic_fixture=False, metadata_dir=root, provenance=provenance
            )
            paths, evidence = helper.resolve_inputs(args, ROOT)
            self.assertEqual(len(paths), 4)
            self.assertEqual(evidence["upstream_revision"], revision)
            for field, bad in (
                ("sha256", "0" * 64),
                ("path", "../escape.tsv"),
                ("url", "https://example.test/"),
            ):
                changed = copy.deepcopy(manifest)
                changed["files"][ROLES[0]][field] = bad
                provenance.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    helper.resolve_inputs(args, ROOT)
            swapped = copy.deepcopy(manifest)
            swapped["files"][ROLES[0]]["url"] = manifest["files"][ROLES[2]]["url"]
            provenance.write_text(json.dumps(swapped))
            with self.assertRaisesRegex(ValueError, "URL/revision"):
                helper.resolve_inputs(args, ROOT)

    def test_synthetic_cli_outputs_private_deterministic_checked_files(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "source"
            (repo / "scripts").mkdir(parents=True)
            (repo / ".gitignore").write_text("/outputs/\n")
            shutil.copyfile(SCRIPT, repo / "scripts" / SCRIPT.name)
            module = repo / "src/perturb_lm/audits"
            module.mkdir(parents=True)
            shutil.copyfile(ROOT / "src/perturb_lm/audits/layouts.py", module / "layouts.py")
            for relative in ("__init__.py", "_version.py", "audits/__init__.py"):
                shutil.copyfile(
                    ROOT / "src/perturb_lm" / relative,
                    repo / "src/perturb_lm" / relative,
                )
            shutil.copytree(FIXTURES, repo / "tests/fixtures/phase5_2")
            # A regular installed package must not displace this fixture's source.
            competing = Path(temp) / "competing-site"
            (competing / "perturb_lm").mkdir(parents=True)
            (competing / "perturb_lm/__init__.py").write_text(
                'raise RuntimeError("Competing package was imported")\n'
            )
            env = dict(
                os.environ,
                PYTHONPATH=os.pathsep.join((str(repo / "src"), str(competing))),
                PYTHONDONTWRITEBYTECODE="1",
            )
            outputs = []
            for name in ("run1", "run2"):
                out = repo / "outputs" / name
                run = subprocess.run(
                    [
                        sys.executable,
                        str(repo / "scripts" / SCRIPT.name),
                        "--synthetic-fixture",
                        "--out",
                        str(out),
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    run.returncode,
                    0,
                    f"CLI failed. stdout:\n{run.stdout}\nstderr:\n{run.stderr}",
                )
                self.assertIn("PROPOSED_NOT_APPROVED", run.stdout)
                summary = json.loads((out / "summary.json").read_text())
                self.assertEqual(summary["evidence_kind"], "synthetic_fixture")
                self.assertFalse(summary["execution_allowed"])
                self.assertEqual(out.stat().st_mode & 0o777, 0o700)
                for line in (out / "SHA256SUMS").read_text().splitlines():
                    digest, filename = line.split("  ")
                    path = out / filename
                    self.assertEqual(sha256(path), digest)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                outputs.append(out)
            for path in outputs[0].iterdir():
                self.assertEqual(path.read_bytes(), (outputs[1] / path.name).read_bytes())


if __name__ == "__main__":
    unittest.main()
