"""Invented JSON receipts only: confinement and same-byte provenance (#30, #52)."""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from perturb_lm.audits import json_inputs
from perturb_lm.audits.json_inputs import read_json_snapshot


class JsonInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "evidence with spaces"
        self.root.mkdir()
        self.path = self.root / "receipt.json"
        self.data = b'{"synthetic": true}\n'
        self.path.write_bytes(self.data)

    def test_value_and_digest_bind_exact_same_snapshot(self):
        snapshot = read_json_snapshot(self.path, root=self.root)
        self.path.write_text('{"replacement": true}')
        self.assertEqual(snapshot.value, {"synthetic": True})
        self.assertEqual(snapshot.sha256, hashlib.sha256(self.data).hexdigest())

    def test_trusted_root_alias_resolves_but_child_aliases_are_rejected(self):
        root_alias = self.root.parent / "trusted-alias"
        root_alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(
            read_json_snapshot(root_alias / self.path.name, root=root_alias).value,
            {"synthetic": True},
        )
        self.assertEqual(
            read_json_snapshot(root_alias / self.path.name, root=self.root).value,
            {"synthetic": True},
        )
        child_alias = self.root / "child-alias.json"
        child_alias.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "regular file|symlink"):
            read_json_snapshot(child_alias, root=self.root)

    def test_outside_sibling_and_symlink_escape_are_rejected_before_read(self):
        sibling = self.root.parent / (self.root.name + "-other")
        sibling.mkdir()
        outside = sibling / "outside.json"
        outside.write_bytes(self.data)
        escaping = self.root / "escape.json"
        escaping.symlink_to(outside)
        with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
            for path in (outside, escaping, self.root / ".." / sibling.name / outside.name):
                with self.subTest(path=path.name), self.assertRaisesRegex(
                    ValueError, "outside|parent traversal"
                ):
                    read_json_snapshot(path, root=self.root)

    def test_symlink_parent_traversal_cannot_select_another_inside_root_file(self):
        subdirectory = self.root / "subdirectory"
        subdirectory.mkdir()
        child = subdirectory / "child"
        child.mkdir()
        (subdirectory / self.path.name).write_bytes(b'{"different": true}')
        alias = self.root / "child-alias"
        alias.symlink_to(child, target_is_directory=True)
        with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
            with self.assertRaisesRegex(ValueError, "parent traversal"):
                read_json_snapshot(alias / ".." / self.path.name, root=self.root)

    def test_directory_and_fifo_never_open_as_a_payload(self):
        fifo = self.root / "fifo.json"
        os.mkfifo(fifo)
        directory = self.root / "directory.json"
        directory.mkdir()
        with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
            for path in (fifo, directory):
                with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, "regular"):
                    read_json_snapshot(path, root=self.root)

    def test_exact_limit_is_allowed_and_oversize_stops_before_payload_read(self):
        with mock.patch.object(json_inputs, "MAX_JSON_BYTES", 64):
            self.path.write_bytes(b"{}" + b" " * 62)
            self.assertEqual(read_json_snapshot(self.path, root=self.root).value, {})
            self.path.write_bytes(b"{}" + b" " * 63)
            with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
                with self.assertRaisesRegex(ValueError, "limit"):
                    read_json_snapshot(self.path, root=self.root)

    def test_invalid_encoding_json_duplicates_constants_and_nonobject_fail(self):
        for data in (
            b"\xff", b"{", b'{"x": 1, "x": 2}', b'{"x": NaN}', b"[]",
            b'{"x": 1e9999}', b'{"x": -1e9999}',
        ):
            self.path.write_bytes(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_json_snapshot(self.path, root=self.root)

    def test_in_place_mutation_during_read_is_rejected(self):
        original_read = os.read
        changed = False

        def mutate(fd, count):
            nonlocal changed
            block = original_read(fd, count)
            if not changed:
                self.path.write_bytes(b'{"replacement": true}\n')
                changed = True
            return block

        with mock.patch.object(json_inputs.os, "read", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed"):
                read_json_snapshot(self.path, root=self.root)

    def test_leaf_replaced_before_open_is_rejected_without_read(self):
        original_open = os.open
        replacement = self.root / "replacement.json"
        replacement.write_bytes(self.data)

        def replace_leaf(path, flags, **kwargs):
            if kwargs.get("dir_fd") is not None and path == self.path.name:
                replacement.replace(self.path)
            return original_open(path, flags, **kwargs)

        # The support-set check concerns the real system call, not this test wrapper.
        support = set(os.supports_dir_fd)
        with mock.patch.object(json_inputs.os, "open", side_effect=replace_leaf) as opened:
            support.add(opened)
            with mock.patch.object(json_inputs.os, "supports_dir_fd", support):
                with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
                    with self.assertRaisesRegex(ValueError, "changed"):
                        read_json_snapshot(self.path, root=self.root)

    def test_parent_replaced_by_symlink_after_check_is_rejected_without_read(self):
        original_open = os.open
        nested = self.root / "nested"
        nested.mkdir()
        path = nested / "receipt.json"
        path.write_bytes(self.data)
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / path.name).write_bytes(b'{"outside": true}')

        def replace_parent(path, flags, **kwargs):
            if kwargs.get("dir_fd") is not None and path == nested.name:
                nested.rename(self.root / "moved")
                nested.symlink_to(outside, target_is_directory=True)
            return original_open(path, flags, **kwargs)

        support = set(os.supports_dir_fd)
        with mock.patch.object(json_inputs.os, "open", side_effect=replace_parent) as opened:
            support.add(opened)
            with mock.patch.object(json_inputs.os, "supports_dir_fd", support):
                with mock.patch.object(json_inputs.os, "read", side_effect=AssertionError("read")):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        read_json_snapshot(path, root=self.root)


def load_cli(name):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(name, root / "scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class JsonCliTests(unittest.TestCase):
    def test_census_cli_uses_snapshot_value_and_digest(self):
        cli = load_cli("audit_phase5_guide_support")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, context = root / "validation.json", root / "context.json"
            validation.write_bytes(b'{"validation": "synthetic"}\n')
            context.write_bytes(b'{"repository": "synthetic"}\n')
            validation_data, context_data = validation.read_bytes(), context.read_bytes()
            output = root / "result"
            argv = [
                "audit", "--audit-root", str(root), "--data-root", str(root),
                "--out", str(output), "--evidence-root", str(root),
                "--validation", str(validation), "--repository-context", str(context),
            ]

            def verify(*_):
                # Later replacement must not change the already captured receipt/digest.
                validation.write_text('{"modified": true}')
                context.write_text('{"modified": true}')
                return None, None, {"input_manifest_sha256": {}}, {}

            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(cli, "guarded_output", return_value=output):
                    with mock.patch.object(cli.subprocess, "check_output", return_value=""):
                        with mock.patch.object(cli, "verify_inputs", side_effect=verify):
                            with mock.patch.object(cli, "support_census", return_value={}):
                                cli.main()
            summary = json.loads((output / "metadata-support-summary.json").read_text())
            self.assertEqual(summary["validation"], {"validation": "synthetic"})
            self.assertEqual(summary["repository_context"], {"repository": "synthetic"})
            self.assertEqual(
                summary["validation_evidence_sha256"], hashlib.sha256(validation_data).hexdigest()
            )
            self.assertEqual(
                summary["repository_context_sha256"], hashlib.sha256(context_data).hexdigest()
            )

    def test_readiness_cli_keeps_both_json_snapshot_digests(self):
        cli = load_cli("prepare_phase5_cross_guide_readiness")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit = root / "audit"
            (audit / "cohort").mkdir(parents=True)
            (audit / "source").mkdir()
            fixture = Path(__file__).parent / "fixtures/phase5_1/rotation_mapping_synthetic.csv"
            rows = cli.read_table(fixture)
            rows["gene"] = rows.Metadata_gene
            rows["target_sequence"] = rows.broad_sample.map({
                "SYNTH_TREAT_A": "ACGTACGT", "SYNTH_TREAT_B": "CGTACGTA",
                "SYNTH_TREAT_C": "GTACGTAC", "SYNTH_CONTROL": "",
            }).fillna("")
            rows["Metadata_target_sequence"] = rows.target_sequence
            annotations = rows[rows.broad_sample.ne("")].drop_duplicates("broad_sample")[[
                "broad_sample", "gene", "target_sequence", "Perturbation",
            ]]
            mapping = audit / "cohort/local_mapping_PRIVATE.csv"
            rows.to_csv(mapping, index=False)
            annotation = audit / "source/JUMP-Target-1_crispr_metadata.tsv"
            annotations.to_csv(annotation, sep="\t", index=False)
            provenance = audit / "source/provenance.json"
            provenance.write_text(json.dumps({"files": [
                {"path": annotation.name, "sha256": cli.checksum(annotation)}
            ]}))
            census = root / "census.json"
            census.write_text(json.dumps({"status": "COMPLETE", "verification": {
                "verified": True, "input_manifest_sha256": {
                    "original_mapping": cli.checksum(mapping),
                    "original_source_provenance": cli.checksum(provenance),
                },
            }}))
            genes = sorted(set(rows.loc[rows.Metadata_pert_type.eq("trt"), "Metadata_gene"]))
            approved = root / "approved.tsv"
            approved.write_text("hgnc_id\tsymbol\tstatus\n" + "".join(
                f"HGNC:{900000001 + index}\t{gene}\tApproved\n"
                for index, gene in enumerate(genes)
            ))
            withdrawn = root / "withdrawn.tsv"
            withdrawn.write_text("HGNC_ID\tSTATUS\tWITHDRAWN_SYMBOL\n")
            reference = root / "reference.json"
            expected_reference = {
                "approved": {"sha256": cli.checksum(approved)},
                "withdrawn": {"sha256": cli.checksum(withdrawn)},
            }
            reference.write_text(json.dumps(expected_reference))
            reference_hash, census_hash = cli.checksum(reference), cli.checksum(census)
            output = root / "result"
            argv = [
                "prepare", "--audit-root", str(audit), "--census-summary", str(census),
                "--expected-summary-sha256", census_hash, "--census-root", str(root),
                "--reference-manifest", str(reference), "--reference-root", str(root),
                "--hgnc-approved", str(approved), "--hgnc-withdrawn", str(withdrawn),
                "--out", str(output),
            ]
            original_table = cli.read_table

            def read_after_replace(path):
                # Existing input bytes remain preserved by their snapshots.
                census.write_text('{"modified": true}')
                reference.write_text('{"modified": true}')
                return original_table(path)

            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(cli, "guarded_output", return_value=output):
                    with mock.patch.object(cli.subprocess, "check_output", return_value=""):
                        with mock.patch.object(cli, "read_table", side_effect=read_after_replace):
                            cli.main()
            summary = json.loads((output / "identity-summary.json").read_text())
            self.assertEqual(summary["census_receipt_sha256"], census_hash)
            self.assertEqual(summary["reference_manifest_sha256"], reference_hash)
            self.assertEqual(summary["HGNC_references"], expected_reference)
            self.assertFalse(summary["scores_computed"])


if __name__ == "__main__":
    unittest.main()
