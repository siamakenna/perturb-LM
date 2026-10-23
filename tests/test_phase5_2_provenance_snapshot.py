"""Invented-fixture tests for a bounded, source-bound provenance manifest snapshot."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_phase5_2_layouts.py"
FIXTURES = ROOT / "tests/fixtures/phase5_2"


def load_script():
    spec = importlib.util.spec_from_file_location("phase52_snapshot_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
        spec.loader.exec_module(module)
    return module


class ProvenanceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_script()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.metadata = self.root / "metadata"
        self.metadata.mkdir()
        revision = "a" * 40
        self.manifest = {
            "schema_version": 1,
            "repository": "jump-cellpainting/JUMP-Target",
            "revision": revision,
            "files": {},
        }
        for role in self.helper.ROLES:
            path = self.metadata / f"{role}.tsv"
            shutil.copyfile(FIXTURES / path.name, path)
            self.manifest["files"][role] = {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "url": (
                    "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/"
                    f"{revision}/{self.helper.SOURCE_FILENAMES[role]}"
                ),
            }
        self.provenance = self.root / "provenance.json"
        self.original = (json.dumps(self.manifest, indent=2) + "\n").encode("utf-8")
        self.provenance.write_bytes(self.original)
        self.args = SimpleNamespace(
            synthetic_fixture=False,
            metadata_dir=self.metadata,
            provenance=self.provenance,
        )

    def test_valid_manifest_exact_bytes_are_recorded_with_source_bindings(self):
        self.assertEqual(self.helper.read_manifest_snapshot(self.provenance), self.original)
        paths, evidence = self.helper.resolve_inputs(self.args, ROOT)
        self.assertEqual(set(paths), set(self.helper.ROLES))
        self.assertEqual(evidence["upstream_revision"], self.manifest["revision"])
        self.assertEqual(
            evidence["source_provenance_manifest_sha256"],
            hashlib.sha256(self.original).hexdigest(),
        )

    def test_exact_byte_limit_is_allowed_and_oversize_fails_before_open(self):
        limit = self.helper.MAX_PROVENANCE_BYTES
        boundary = b" " * (limit - 2) + b"{}"
        self.provenance.write_bytes(boundary)
        self.assertEqual(self.helper.read_manifest_snapshot(self.provenance), boundary)
        with self.provenance.open("wb") as stream:
            stream.truncate(limit + 1)
        with mock.patch.object(self.helper.os, "open", wraps=os.open) as opened:
            with self.assertRaisesRegex(ValueError, "bounded regular"):
                self.helper.resolve_inputs(self.args, ROOT)
        self.assertNotIn(self.provenance.name, [call.args[0] for call in opened.call_args_list])

    def test_missing_manifest_fails_closed(self):
        self.provenance.unlink()
        with self.assertRaisesRegex(ValueError, "missing, unreadable, or unsafe"):
            self.helper.resolve_inputs(self.args, ROOT)

    def test_leaf_symlink_is_rejected_before_open(self):
        saved = self.root / "saved-manifest.json"
        self.provenance.rename(saved)
        self.provenance.symlink_to(saved)
        with mock.patch.object(self.helper.os, "open", wraps=os.open) as opened:
            with self.assertRaisesRegex(ValueError, "nonsymlink"):
                self.helper.resolve_inputs(self.args, ROOT)
        self.assertNotIn(self.provenance.name, [call.args[0] for call in opened.call_args_list])
        self.assertEqual(saved.read_bytes(), self.original)

    def test_directory_fifo_and_device_are_rejected_without_opening(self):
        directory = self.root / "directory"
        directory.mkdir()
        with mock.patch.object(self.helper.os, "open", wraps=os.open) as opened:
            with self.assertRaisesRegex(ValueError, "regular"):
                self.helper.read_manifest_snapshot(directory)
        self.assertNotIn(self.provenance.name, [call.args[0] for call in opened.call_args_list])
        if hasattr(os, "mkfifo"):
            fifo = self.root / "input.fifo"
            os.mkfifo(fifo)
            with mock.patch.object(self.helper.os, "open", wraps=os.open) as opened:
                with self.assertRaisesRegex(ValueError, "regular"):
                    self.helper.read_manifest_snapshot(fifo)
            self.assertNotIn(self.provenance.name, [call.args[0] for call in opened.call_args_list])
        # Substitute only the leaf's stat description; no device is accessed.
        original_stat = os.stat
        device = SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_size=0)
        def device_stat(path, *args, **kwargs):
            if path == self.provenance.name and kwargs.get("dir_fd") is not None:
                return device
            return original_stat(path, *args, **kwargs)
        with mock.patch.object(self.helper.os, "stat", side_effect=device_stat):
            with mock.patch.object(self.helper.os, "open", wraps=os.open) as opened:
                with self.assertRaisesRegex(ValueError, "regular"):
                    self.helper.read_manifest_snapshot(self.provenance)
            self.assertNotIn(self.provenance.name, [call.args[0] for call in opened.call_args_list])

    def test_replacement_between_lstat_and_open_is_rejected(self):
        original_open = os.open

        def replace_before_open(path, flags, *args, **kwargs):
            if path == self.provenance.name:
                self.provenance.rename(self.root / "first-inode.json")
                self.provenance.write_bytes(self.original)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(self.helper.os, "open", side_effect=replace_before_open):
            with self.assertRaisesRegex(ValueError, "changed while opening"):
                self.helper.read_manifest_snapshot(self.provenance)

    def test_in_place_change_during_read_is_rejected(self):
        original_read = os.read
        changed = False
        old_mtime = self.provenance.stat().st_mtime_ns

        def change_after_read(descriptor, size):
            nonlocal changed
            block = original_read(descriptor, size)
            if block and not changed:
                changed = True
                self.provenance.write_bytes(self.original.replace(b"a" * 40, b"b" * 40))
                os.utime(self.provenance, ns=(old_mtime + 1, old_mtime + 1))
            return block

        with mock.patch.object(self.helper.os, "read", side_effect=change_after_read):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                self.helper.read_manifest_snapshot(self.provenance)

    def test_unreadable_open_error_is_reported_as_invalid_provenance(self):
        with mock.patch.object(self.helper.os, "open", side_effect=PermissionError("fixture")):
            with self.assertRaisesRegex(ValueError, "unreadable"):
                self.helper.resolve_inputs(self.args, ROOT)

    def test_completed_audit_hashes_parsed_snapshot_after_in_place_manifest_edit(self):
        # Exercise main through completed outputs in a disposable source archive.
        # The only inputs are the repository's invented four-table fixture.
        repository = self.root / "source"
        (repository / "scripts").mkdir(parents=True)
        (repository / "src/perturb_lm/audits").mkdir(parents=True)
        (repository / "outputs").mkdir()
        (repository / ".gitignore").write_text("/outputs/\n")
        source_script = repository / "scripts/audit_phase5_2_layouts.py"
        shutil.copyfile(SCRIPT, source_script)
        helper_dir = repository / "scripts/phase5_2_batch8_pilot"
        helper_dir.mkdir()
        shutil.copyfile(ROOT / "scripts/phase5_2_batch8_pilot/path_contract.py",
                        helper_dir / "path_contract.py")
        shutil.copyfile(
            ROOT / "src/perturb_lm/audits/layouts.py",
            repository / "src/perturb_lm/audits/layouts.py",
        )
        output = repository / "outputs/audit"
        original_sha256 = self.helper.sha256
        changed = False
        replacement = dict(self.manifest, revision="b" * 40)
        replacement_bytes = (json.dumps(replacement, indent=2) + "\n").encode("utf-8")
        self.assertEqual(len(self.original), len(replacement_bytes))

        def edit_manifest_during_source_validation(path):
            nonlocal changed
            if Path(path).parent == self.metadata and not changed:
                changed = True
                self.provenance.write_bytes(replacement_bytes)
            return original_sha256(path)

        argv = [
            str(source_script), "--metadata-dir", str(self.metadata),
            "--provenance", str(self.provenance), "--out", str(output),
        ]
        with (
            mock.patch.object(self.helper, "__file__", str(source_script)),
            mock.patch.object(
                self.helper, "sha256", side_effect=edit_manifest_during_source_validation
            ),
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.helper.main()
        self.assertTrue(changed)
        summary = json.loads((output / "summary.json").read_bytes())
        self.assertEqual(summary["upstream_revision"], "a" * 40)
        self.assertEqual(
            summary["source_provenance_manifest_sha256"],
            hashlib.sha256(self.original).hexdigest(),
        )
        self.assertNotEqual(
            summary["source_provenance_manifest_sha256"],
            hashlib.sha256(self.provenance.read_bytes()).hexdigest(),
        )
        self.assertTrue((output / "SHA256SUMS").is_file())
        for line in (output / "SHA256SUMS").read_text().splitlines():
            expected, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
