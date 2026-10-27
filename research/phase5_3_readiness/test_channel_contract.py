"""Invented file fixtures only; this suite does not validate real microscopy."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import channel_contract as contract


class ChannelContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "raw").mkdir()
        self.path = self.root / "inventory.json"
        self.data = {"status": "raw_download_complete", "files": [],
                     "channel_mapping": {c: "File_" + c for c in contract.CHANNELS}}
        for site in (1, 2):
            for index, channel in enumerate(contract.CHANNELS):
                relative = "raw/site%d_%s.tiff" % (site, channel)
                raw = b"II*\x00\x08\x00\x00\x00" + bytes((site, index)) * 8
                (self.root / relative).write_bytes(raw)
                self.data["files"].append({
                    "record_id": "field%d" % site, "batch": "invented_batch", "plate": "P001",
                    "well": "A0%d" % site, "site": 1, "channel": channel,
                    "mapping_column": "File_" + channel, "path": relative,
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "pixelWidth": 12, "pixelHeight": 8, "bitsPerSample": 16, "samplesPerPixel": 1})

    def write(self, data=None):
        raw = (json.dumps(self.data if data is None else data) + "\n").encode()
        self.path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def inspect(self, data=None):
        return contract.inspect_inventory(self.path, expected_sha256=self.write(data))

    def test_complete_groups_verify_bytes_and_preserve_scientific_limits(self):
        result = self.inspect()
        self.assertEqual(result["image_fields"], 2)
        self.assertEqual(result["channel_files"], 10)
        self.assertEqual(result["channels"], list(contract.CHANNELS))
        self.assertTrue(result["input_bytes_verified"])
        for field in ("pixels_decoded", "model_inference_performed", "header_dimensions_verified",
                      "channel_registration_verified", "study_cohort_established"):
            self.assertFalse(result[field])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertNotIn("field1", json.dumps(result))

    def test_input_reordering_preserves_aggregates(self):
        original = self.inspect()
        self.data["files"].reverse()
        changed = self.inspect()
        original.pop("inventory_sha256"); changed.pop("inventory_sha256")
        self.assertEqual(original, changed)

    def test_inventory_hash_mismatch_precedes_image_access(self):
        self.write()
        for path in (self.root / "raw").iterdir():
            path.unlink()
        with self.assertRaisesRegex(ValueError, "Inventory checksum"):
            contract.inspect_inventory(self.path, "0" * 64)

    def test_missing_channel_is_not_a_valid_complete_group(self):
        self.data["files"].pop()
        with self.assertRaisesRegex(ValueError, "all five"):
            self.inspect()

    def test_duplicate_channel_and_conflicting_field_identity_fail(self):
        row = self.data["files"][1]
        row["channel"] = "DNA"; row["mapping_column"] = "File_DNA"
        with self.assertRaisesRegex(ValueError, "Duplicate fluorescence"):
            self.inspect()
        row["channel"] = "ER"; row["mapping_column"] = "File_ER"; row["well"] = "B01"
        with self.assertRaisesRegex(ValueError, "Conflicting identity"):
            self.inspect()

    def test_duplicate_record_alias_for_same_field_fails(self):
        for row in self.data["files"][5:]:
            row["well"] = "A01"
        with self.assertRaisesRegex(ValueError, "Duplicate image-field"):
            self.inspect()

    def test_absolute_traversal_and_noncanonical_paths_fail(self):
        original = self.data["files"][0]["path"]
        for relative in ("../outside.tif", "/tmp/outside.tif", "raw/../x.tif", "raw//x.tif",
                         "raw\\x.tif", "C:/x.tif", ".", "raw/new\nline.tif"):
            with self.subTest(relative=relative):
                self.data["files"][0]["path"] = relative
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    self.inspect()
        self.data["files"][0]["path"] = original

    def test_internal_file_and_directory_symlinks_are_rejected(self):
        original = self.root / self.data["files"][0]["path"]
        target = self.root / "original.tif"
        original.rename(target)
        original.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.inspect()
        original.unlink(); target.rename(original)
        (self.root / "raw").rename(self.root / "actual_raw")
        (self.root / "raw").symlink_to(self.root / "actual_raw", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.inspect()

    def test_ancestor_alias_is_supported_but_inventory_symlink_fails(self):
        expected = self.write()
        alias = self.root.parent / (self.root.name + "-alias")
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        result = contract.inspect_inventory(alias / self.path.name, expected)
        self.assertEqual(result["channel_files"], 10)
        linked = self.root / "linked.json"
        linked.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            contract.inspect_inventory(linked, expected)

    def test_tampered_bytes_and_size_fail(self):
        image = self.root / self.data["files"][0]["path"]
        raw = image.read_bytes()
        image.write_bytes(raw[:-1] + b"x")
        with self.assertRaisesRegex(ValueError, "Image checksum"):
            self.inspect()
        image.write_bytes(raw + b"x")
        with self.assertRaisesRegex(ValueError, "byte size"):
            self.inspect()

    def test_updated_hash_does_not_make_nontiff_bytes_valid(self):
        row = self.data["files"][0]
        image = self.root / row["path"]
        raw = b"not tiff" + b"x" * (row["bytes"] - 8)
        image.write_bytes(raw); row["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, "TIFF signature"):
            self.inspect()

    def test_all_four_supported_tiff_signatures_are_accepted(self):
        for prefix in (b"II*\x00\x08\x00\x00\x00", b"MM\x00*\x00\x00\x00\x08",
                       b"II+\x00\x08\x00\x00\x00", b"MM\x00+\x00\x08\x00\x00"):
            with self.subTest(prefix=prefix):
                row = self.data["files"][0]; image = self.root / row["path"]
                raw = prefix + image.read_bytes()[8:]
                image.write_bytes(raw); row["sha256"] = hashlib.sha256(raw).hexdigest()
                self.assertEqual(self.inspect()["image_fields"], 2)

    def test_declared_dimensions_mapping_wells_and_aggregate_contradictions_fail(self):
        cases = (("pixelWidth", 9), ("mapping_column", "File_wrong"), ("well", "A1"),
                 ("site", True), ("samplesPerPixel", 3))
        for field, value in cases:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data); data["files"][0][field] = value
                with self.assertRaises(ValueError):
                    self.inspect(data)
        self.data["site_count"] = 3
        with self.assertRaisesRegex(ValueError, "aggregate count"):
            self.inspect()

    def test_file_site_and_total_byte_limits_fail_without_large_files(self):
        with patch.object(contract, "MAX_FILES", 9):
            with self.assertRaisesRegex(ValueError, "file-count"):
                self.inspect()
        with patch.object(contract, "MAX_SITES", 1):
            with self.assertRaisesRegex(ValueError, "image-field limit"):
                self.inspect()
        with patch.object(contract, "MAX_TOTAL_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "total byte"):
                self.inspect()
        self.data["files"][0]["bytes"] = contract.MAX_FILE_BYTES + 1
        with self.assertRaisesRegex(ValueError, "image bytes"):
            self.inspect()

    def test_duplicate_input_path_and_hardlink_alias_fail(self):
        self.data["files"][1]["path"] = self.data["files"][0]["path"]
        with self.assertRaisesRegex(ValueError, "Duplicate image input path"):
            self.inspect()
        self.data["files"][1]["path"] = "raw/site1_ER.tiff"
        image = self.root / self.data["files"][1]["path"]
        image.unlink(); os.link(self.root / self.data["files"][0]["path"], image)
        with self.assertRaisesRegex(ValueError, "same physical input"):
            self.inspect()

    def test_duplicate_json_keys_and_json_byte_limit_fail(self):
        raw = b'{"status":"raw_download_complete","status":"raw_download_complete"}'
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            contract.inspect_inventory(self.path, hashlib.sha256(raw).hexdigest())
        expected = self.write()
        with patch.object(contract, "MAX_JSON_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "JSON exceeds"):
                contract.inspect_inventory(self.path, expected)

    def test_missing_parent_is_reported_as_bounded_input_blocker(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            contract.inspect_inventory(self.root / "missing/staging/inventory.json")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires POSIX")
    def test_nonregular_fifo_is_rejected_without_waiting_for_a_writer(self):
        image = self.root / self.data["files"][0]["path"]
        image.unlink(); os.mkfifo(image)
        with self.assertRaisesRegex(ValueError, "regular files"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
