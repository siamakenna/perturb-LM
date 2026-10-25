"""Invented filesystem regressions for the Batch8 operator-path boundary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

import control_utils
import prepare
from path_contract import PathContract, exclusive_write_json, read_bytes


class PathContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="batch8-path-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("/outputs/\n")
        self.outputs = self.repo / "outputs"
        self.outputs.mkdir()
        self.contract = PathContract(self.root)
        self.layout = self.root / "layout.csv"
        self.qc = self.root / "qc.json"
        self.layout.write_text("INVENTED_LAYOUT_ONLY\n")
        self.qc.write_text("{}\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout

    def test_valid_fresh_private_output_and_exclusive_result(self):
        out = self.contract.create_output(self.outputs / "new")
        self.contract.write_json(out / "result.json", {"invented": True})
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((out / "result.json").stat().st_mode), 0o600)
        self.assertEqual(json.loads((out / "result.json").read_text()), {"invented": True})

    def test_outside_outputs_rejected_before_prepare_creates_anything(self):
        out = self.root / "outside-results"
        with self.assertRaises(ValueError):
            prepare.prepare(self.root, out)
        self.assertFalse(out.exists())

    def test_outside_outputs_rejected_before_control_lookup_or_fetch(self):
        out = self.root / "outside-controls"
        with mock.patch.object(control_utils, "fetch_file") as fetch:
            with self.assertRaises(ValueError):
                control_utils.run(self.layout, self.qc, out, work_root=self.root)
            fetch.assert_not_called()
        self.assertFalse(out.exists())

    def test_existing_output_and_contents_preserved(self):
        out = self.contract.create_output(self.outputs / "existing")
        sentinel = out / "keep.txt"
        sentinel.write_text("keep\n")
        with self.assertRaises(FileExistsError):
            self.contract.create_output(out)
        self.assertEqual(sentinel.read_text(), "keep\n")
        self.assertEqual(list(out.iterdir()), [sentinel])

    def test_internal_directory_symlink_rejected_even_when_target_is_inside_root(self):
        target = self.root / "other"
        target.mkdir()
        alias = self.outputs / "alias"
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            self.contract.create_output(alias / "new")
        self.assertFalse((target / "new").exists())

    def test_escaping_dotdot_rejected(self):
        with self.assertRaises(ValueError):
            self.contract.create_output(self.outputs / ".." / ".." / "escape")
        self.assertFalse((self.root / "escape").exists())

    def test_os_ancestor_alias_allowed_without_changing_canonical_destination(self):
        alias = self.root.parent / (self.root.name + "-os-alias")
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        contract = PathContract(alias)
        out = contract.create_output(alias / "repo" / "outputs" / "new")
        self.assertEqual(out, self.outputs / "new")
        self.assertEqual(contract.work_root, self.root)

    def test_existing_repository_and_ignored_outputs_are_required(self):
        (self.repo / ".gitignore").write_text("")
        with self.assertRaisesRegex(ValueError, "Git ignored"):
            self.contract.create_output(self.outputs / "new")
        self.assertFalse((self.outputs / "new").exists())

    def test_tracked_prefix_rejected_even_when_path_is_ignored_and_absent(self):
        out = self.outputs / "tracked"
        out.mkdir()
        (out / "old.txt").write_text("invented tracked fixture")
        self.git("add", "-f", "outputs/tracked/old.txt")
        shutil.rmtree(out)
        with self.assertRaisesRegex(ValueError, "tracked"):
            self.contract.create_output(out)

    def test_pointer_to_existing_inside_directory_is_allowed(self):
        directory = self.root / "public"
        directory.mkdir()
        (self.root / "latest-public-layouts.txt").write_text(str(directory) + "\n")
        self.assertEqual(self.contract.read_pointer("latest-public-layouts"), directory)

    def test_pointer_escape_and_pointer_symlink_rejected(self):
        pointer = self.root / "latest-public-layouts.txt"
        pointer.write_text(str(self.root.parent))
        with self.assertRaisesRegex(ValueError, "Invalid recorded location"):
            self.contract.read_pointer("latest-public-layouts")
        pointer.unlink()
        victim = self.root / "pointer-content"
        victim.write_text(str(self.root))
        pointer.symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "Invalid recorded location"):
            self.contract.read_pointer("latest-public-layouts")

    def test_pointer_relative_multiline_oversized_and_unknown_names_rejected(self):
        pointer = self.root / "latest-public-layouts.txt"
        for body in ("relative", str(self.root) + "\n" + str(self.outputs), "x" * 5000):
            with self.subTest(body=body[:30]):
                pointer.write_text(body)
                with self.assertRaisesRegex(ValueError, "Invalid recorded location"):
                    self.contract.read_pointer("latest-public-layouts")
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.contract.read_pointer("../../outside")

    def test_regular_file_byte_bound_symlink_and_fifo_are_checked_before_reading(self):
        data = self.root / "input.txt"
        data.write_bytes(b"12345")
        with self.assertRaises(ValueError):
            self.contract.read_bytes(data, max_bytes=4)
        alias = self.root / "input-alias"
        alias.symlink_to(data)
        with self.assertRaises(ValueError):
            self.contract.read_bytes(alias)
        with self.assertRaises(ValueError):
            read_bytes(alias)
        if hasattr(os, "mkfifo"):
            fifo = self.root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                read_bytes(fifo)

    def test_existing_file_or_link_cannot_be_overwritten(self):
        out = self.contract.create_output(self.outputs / "new")
        existing = out / "result.json"
        existing.write_text("preserve")
        with self.assertRaises(FileExistsError):
            self.contract.write_json(existing, {"replace": True})
        self.assertEqual(existing.read_text(), "preserve")
        victim = self.root / "victim.txt"
        victim.write_text("keep victim")
        link = out / "linked.json"
        link.symlink_to(victim)
        with self.assertRaises(ValueError):
            self.contract.write_json(link, {})
        with self.assertRaises(FileExistsError):
            exclusive_write_json(link, {})
        self.assertEqual(victim.read_text(), "keep victim")

    def test_output_cannot_nest_inside_plan_input(self):
        plan = self.contract.create_output(self.outputs / "plan")
        with self.assertRaisesRegex(ValueError, "overlaps"):
            self.contract.create_output(plan / "nested", forbidden=[plan])

    def test_run_directory_prefix_cannot_escape_output_root(self):
        with self.assertRaises(ValueError):
            self.contract.create_run_directory("../../escape")
        run = self.contract.create_run_directory("phase52-pilot.")
        self.assertEqual(run.parent, self.outputs)
        self.assertEqual(stat.S_IMODE(run.stat().st_mode), 0o700)

    def test_run_directory_rejects_forced_tracked_descendant_before_log_creation(self):
        import path_contract
        predicted = self.outputs / "run.fixed-fixture"
        predicted.mkdir()
        (predicted / "old.txt").write_text("invented tracked fixture")
        self.git("add", "-f", "outputs/run.fixed-fixture/old.txt")
        shutil.rmtree(predicted)

        with mock.patch.object(path_contract.secrets, "token_hex", return_value="fixed-fixture"):
            with self.assertRaisesRegex(ValueError, "tracked"):
                self.contract.create_run_directory("run.")
        self.assertFalse(predicted.exists())

    def test_fixed_download_bytes_are_receipt_checked_and_written_exclusively(self):
        out = self.contract.create_output(self.outputs / "controls")
        body = b"INVENTED_PUBLIC_METADATA\n"
        relative = "metadata/perturbation_control.csv"
        api = {"type": "file", "path": relative, "size": len(body),
               "sha": hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()}
        original_run = subprocess.run

        def command(args, **kwargs):
            if args[0] == "git":
                return original_run(args, **kwargs)
            if args[0] == "gh":
                return subprocess.CompletedProcess(args, 0, json.dumps(api).encode(), b"")
            self.assertEqual(args[0], "curl")
            self.assertEqual(args[args.index("--output") + 1], "-")
            kwargs["stdout"].write(body)
            return subprocess.CompletedProcess(args, 0)

        with mock.patch.object(control_utils.subprocess, "run", side_effect=command):
            receipt = control_utils.fetch_file(relative, 64 * 1024, out, contract=self.contract)
        self.assertEqual((out / "perturbation_control.csv").read_bytes(), body)
        self.assertEqual(receipt["sha256"], hashlib.sha256(body).hexdigest())
        self.assertFalse((out / "perturbation_control.csv.partial").exists())


class DescriptorRaceTests(unittest.TestCase):
    setUp = PathContractTests.setUp
    git = PathContractTests.git
    """Controlled swaps use invented files; no research paths or profile values."""

    def test_read_does_not_follow_parent_replaced_after_descriptor_acquisition(self):
        directory = self.root / "incoming"
        directory.mkdir()
        path = directory / "data.txt"
        path.write_bytes(b"INSIDE")
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        (outside / path.name).write_bytes(b"OUTSIDE")
        held = self.root / "held-incoming"
        original_open = os.open
        changed = False

        def swap_at_leaf(name, flags, *args, **kwargs):
            nonlocal changed
            if name == path.name and kwargs.get("dir_fd") is not None and not changed:
                changed = True
                directory.rename(held)
                directory.symlink_to(outside, target_is_directory=True)
            return original_open(name, flags, *args, **kwargs)

        with mock.patch.object(os, "open", side_effect=swap_at_leaf):
            self.assertEqual(read_bytes(path, root=self.root), b"INSIDE")
        self.assertTrue(changed)
        with self.assertRaises(ValueError):
            self.contract.read_bytes(path)

    def test_exclusive_write_cannot_be_redirected_by_parent_swap(self):
        out = self.contract.create_output(self.outputs / "result-dir")
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        held = self.outputs / "held-dir"
        original_open = os.open
        changed = False

        def swap_at_leaf(name, flags, *args, **kwargs):
            nonlocal changed
            if name == "result.json" and flags & os.O_CREAT and not changed:
                changed = True
                out.rename(held)
                out.symlink_to(outside, target_is_directory=True)
            return original_open(name, flags, *args, **kwargs)

        with mock.patch.object(os, "open", side_effect=swap_at_leaf):
            self.contract.write_json(out / "result.json", {"invented": True})
        self.assertTrue(changed)
        self.assertFalse((outside / "result.json").exists())
        self.assertEqual(json.loads((held / "result.json").read_text()), {"invented": True})

    def test_directory_creation_cannot_be_redirected_by_parent_swap(self):
        parent = self.outputs / "parent"
        parent.mkdir()
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        held = self.outputs / "held-parent"
        original_mkdir = os.mkdir
        changed = False

        def swap_at_mkdir(name, *args, **kwargs):
            nonlocal changed
            if name == "new" and kwargs.get("dir_fd") is not None:
                changed = True
                parent.rename(held)
                parent.symlink_to(outside, target_is_directory=True)
            return original_mkdir(name, *args, **kwargs)

        with mock.patch.object(os, "mkdir", side_effect=swap_at_mkdir):
            self.contract.create_output(parent / "new")
        self.assertTrue(changed)
        self.assertFalse((outside / "new").exists())
        self.assertTrue((held / "new").is_dir())

    def test_same_size_rewrite_with_restored_mtime_is_detected(self):
        path = self.root / "snapshot.txt"
        path.write_bytes(b"ORIGINAL")
        stamp = path.stat().st_mtime_ns
        original_read = os.read
        changed = False

        def rewrite(descriptor, size):
            nonlocal changed
            block = original_read(descriptor, size)
            if block and not changed:
                changed = True
                path.write_bytes(b"REPLACED")
                os.utime(path, ns=(stamp, stamp))
            return block

        with mock.patch.object(os, "read", side_effect=rewrite):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                self.contract.read_bytes(path)

    def test_work_root_must_be_an_existing_directory(self):
        for root in (self.root / "absent", self.layout):
            with self.subTest(root=root.name):
                with self.assertRaisesRegex(ValueError, "existing trusted work root"):
                    PathContract(root)

    def test_component_prefix_sibling_is_not_inside_root(self):
        outside = self.root.parent / (self.root.name + "-sibling")
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        path = outside / "data.txt"
        path.write_bytes(b"OUTSIDE")
        with self.assertRaises(ValueError):
            read_bytes(path, root=self.root)


class MetadataPlanTamperTests(unittest.TestCase):
    def test_bound_input_mutation_after_derivation_prevents_a_completed_plan(self):
        # Reuse the existing invented receipt fixture, not any research files.
        import test_prepare
        fixture = test_prepare.InputBindingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        module = test_prepare.m
        repo = fixture.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True,
                       capture_output=True)
        (repo / ".gitignore").write_text("/outputs/\n")
        outputs = repo / "outputs"
        outputs.mkdir()
        out = outputs / "new-plan"
        counts = {"dmso_wells": {plate: 64 for plate in prepare.PLATES},
                  "gallery_population": 1, "query_population": 1,
                  "evaluable_queries": 1, "queries_without_positive": 0}

        def mutate_after_derivation(*args):
            target = fixture.paths["layout"]
            target.write_bytes(b"X" * target.stat().st_size)
            return {"fixture": "invented, no query result"}

        import query_info
        with (
            mock.patch.object(control_utils, "load_reviewed_inputs", return_value=({}, {})),
            mock.patch.object(control_utils, "read_control_registry", return_value={}),
            mock.patch.object(control_utils, "read_selected_wells", return_value={}),
            mock.patch.object(module, "build_cohort", return_value=({"fixture": "invented"}, counts)),
            mock.patch.object(query_info, "analyze", side_effect=mutate_after_derivation),
        ):
            with self.assertRaisesRegex(ValueError, "changed or is missing"):
                module.prepare(fixture.root, out)
        self.assertFalse((out / "plan.json").exists())
        self.assertFalse((out / "SHA256SUMS").exists())
        failure = json.loads((out / "preparation-error.json").read_text())
        self.assertEqual(failure["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
