"""Invented tables and mocked network only; no real-data scientific claims."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import public_inputs as inputs


def table_bytes(frame, sep=","):
    return frame.to_csv(index=False, sep=sep, lineterminator="\n").encode()


def synthetic_tables():
    """384 invented wells per plate, with 30 controls and one blank label."""
    wells = [f"{letter}{column:02d}" for letter in "ABCDEFGHIJKLMNOP" for column in range(1, 25)]
    assignments = ["" if i == 0 else "SYNTH_CTRL" if i <= 30 else "SYNTH_A" if i % 2 else "SYNTH_B" for i in range(384)]
    annotation = pd.DataFrame([
        dict(broad_sample="SYNTH_A", gene="SYNTH_GENE_A", target_sequence="ACGTAC", pert_type="trt", control_type="", negcon_control_type=""),
        dict(broad_sample="SYNTH_B", gene="SYNTH_GENE_B", target_sequence="TGCATG", pert_type="trt", control_type="", negcon_control_type=""),
        dict(broad_sample="SYNTH_CTRL", gene="", target_sequence="", pert_type="negcon", control_type="negcon", negcon_control_type="SYNTH_CONTROL"),
    ])
    lookup = annotation.set_index("broad_sample").to_dict(orient="index")
    conditions = dict(zip(inputs.CONDITIONS, ("crispr", "A549", "144", "100", "absent", "Cas9", "Day0", "1", "none"), strict=True))
    experiments = pd.DataFrame([
        {"Batch": inputs.BATCH, "Assay_Plate_Barcode": plate,
         "Plate_Map_Name": "JUMP-Target-1_crispr_platemap", **conditions}
        for plate in inputs.PLATES
    ])
    sources = {
        "experiment-metadata.tsv": table_bytes(experiments, "\t"),
        "barcode_platemap.csv": table_bytes(experiments[["Assay_Plate_Barcode", "Plate_Map_Name"]]),
        "README.md": b"Invented test fixture, not upstream data.\n",
        "0.create-experiment-metadata.ipynb": b"{}\n",
        "JUMP-Target-1_compound_metadata_targets.tsv": b"broad_sample\ttarget\ttarget_list\n",
    }
    for modality in ("compound", "crispr", "orf"):
        sources[f"JUMP-Target-1_{modality}_platemap.txt"] = table_bytes(pd.DataFrame({"well_position": wells, "broad_sample": assignments}), "\t")
        sources[f"JUMP-Target-1_{modality}_metadata.tsv"] = table_bytes(annotation, "\t")
    frames = {}
    for p, path in enumerate(inputs.PROFILE_PATHS):
        records = []
        for i, (well, reagent) in enumerate(zip(wells, assignments, strict=True)):
            ann = lookup.get(reagent, {})
            records.append({
                "Metadata_Plate": inputs.PLATES[p], "Metadata_Well": well,
                "Metadata_broad_sample": reagent,
                **{f"Metadata_{name}": ann.get(name, "") for name in ("gene", "target_sequence", "pert_type", "control_type", "negcon_control_type")},
                "Cells_SYNTH": str(p * 1000 + i), "Cytoplasm_SYNTH": str(i + 0.5),
            })
        frames[path] = pd.DataFrame(records)
    return sources, frames


class PublicInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="public-input-test-", dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources, self.frames = synthetic_tables()

    def capture(self, name="capture", *, raw_overrides=None, media_override=None):
        compressed = {path: gzip.compress(table_bytes(frame), mtime=0) for path, frame in self.frames.items()}
        pointers = {
            path: f"version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n".encode()
            for path, data in compressed.items()
        }
        raw = {path: self.sources[Path(path).name] for path in inputs.SOURCE_PATHS}
        raw.update(pointers)
        raw.update(raw_overrides or {})
        media = {inputs._media_url(path): data for path, data in compressed.items()}
        if media_override:
            media_override(media)
        self.raw_calls, self.media_calls = [], []

        def get_raw(path, limit, gh):
            self.raw_calls.append((path, limit, gh))
            return raw[path]

        def download(url, limit):
            self.media_calls.append((url, limit))
            result = media[url]
            if len(result) > limit:
                raise ValueError("mock stream exceeds byte bound")
            return result

        with patch.object(inputs, "_get_raw", side_effect=get_raw), patch.object(inputs, "_download_url", side_effect=download):
            return inputs.fetch_public_inputs(self.root / name)

    def load(self, result):
        return inputs.load_study_inputs(Path(result["staging"]))

    def test_complete_capture_and_aligned_all_rows(self):
        captured = self.capture()
        result = self.load(captured)
        metadata, features = result["metadata"], result["features"]
        self.assertEqual(list(metadata), list(inputs.METADATA_COLUMNS))
        self.assertEqual(features.shape, (1536, 2))
        self.assertEqual(set(metadata.plate), set(inputs.PLATES))
        self.assertEqual(metadata.treatment.dtype, bool)
        self.assertEqual(metadata.control.dtype, bool)
        self.assertEqual(int(metadata.treatment.sum()), 1412)
        self.assertEqual(int(metadata.control.sum()), 120)
        self.assertEqual(result["receipt"]["missing_label_rows"], 4)
        self.assertFalse(metadata.loc[metadata.reagent.eq(""), ["treatment", "control"]].any().any())
        self.assertTrue(metadata.condition.map(lambda x: isinstance(x, str) and len(json.loads(x)) == 9).all())
        for index in (0, 383, 384, 1535):
            self.assertEqual(features[index, 0], (index // 384) * 1000 + index % 384)
        self.assertFalse(result["receipt"]["original_twelve_file_cohort_verified"])
        self.assertEqual(result["receipt"]["cohort_origin"], inputs.ORIGIN)
        self.assertEqual(result["receipt"]["upstream_normalization_scope"], "source_batch_global")
        self.assertEqual(Path(captured["staging"]).stat().st_mode & 0o777, 0o700)

    def test_only_fixed_allowlist_requested(self):
        self.capture()
        self.assertEqual([x[0] for x in self.raw_calls], [*inputs.SOURCE_PATHS, *inputs.PROFILE_PATHS])
        self.assertEqual([x[0] for x in self.media_calls], [inputs._media_url(p) for p in inputs.PROFILE_PATHS])
        self.assertTrue(all(inputs.REVISION in url for url, _ in self.media_calls))

    def test_nonfinite_retained_but_bad_text_rejected(self):
        frame = self.frames[inputs.PROFILE_PATHS[0]]
        frame.loc[0:3, "Cells_SYNTH"] = ["nan", "inf", "-inf", ""]
        result = self.load(self.capture())
        self.assertTrue(np.isnan(result["features"][0, 0]))
        self.assertTrue(np.isposinf(result["features"][1, 0]))
        self.assertTrue(np.isneginf(result["features"][2, 0]))
        self.assertTrue(np.isnan(result["features"][3, 0]))
        self.assertEqual(result["receipt"]["nonfinite_feature_values_retained"], 4)
        frame.loc[0, "Cells_SYNTH"] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "nonnumeric"):
            self.load(self.capture("bad-text"))

    def test_bad_lfs_hash_leaves_rejected_partial_capture(self):
        def corrupt(media):
            url = inputs._media_url(inputs.PROFILE_PATHS[0])
            original = media[url]
            media[url] = original[:-1] + bytes([original[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "LFS size and SHA-256"):
            self.capture(media_override=corrupt)
        self.assertTrue((self.root / "capture" / "CAPTURE_INCOMPLETE").is_file())
        self.assertFalse((self.root / "capture" / "manifest.json").exists())
        with self.assertRaisesRegex(ValueError, "Partial"):
            inputs.load_study_inputs(self.root / "capture")

    def test_oversized_lfs_pointer_stops_before_media(self):
        pointer = f"version https://git-lfs.github.com/spec/v1\noid sha256:{'0' * 64}\nsize {inputs.MAX_PROFILE_BYTES + 1}\n".encode()
        with self.assertRaisesRegex(ValueError, "16 MiB"):
            self.capture(raw_overrides={inputs.PROFILE_PATHS[0]: pointer})
        self.assertEqual(self.media_calls, [])

    def test_oversized_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            self.capture(raw_overrides={inputs.SOURCE_PATHS[0]: b"x" * (inputs.MAX_SOURCE_BYTES + 1)})
        self.assertEqual(self.media_calls, [])

    def test_non_lfs_profile_refused(self):
        with self.assertRaisesRegex(ValueError, "Git LFS pointer"):
            self.capture(raw_overrides={inputs.PROFILE_PATHS[0]: b"ordinary csv,not an LFS pointer\n"})
        self.assertEqual(self.media_calls, [])

    def test_receipts_checked_before_decompression_or_feature_load(self):
        for name, relative in (("profile", inputs.PROFILE_PATHS[0]), ("source", "source/experiment-metadata.tsv")):
            with self.subTest(name=name):
                captured = self.capture(name)
                path = Path(captured["staging"]) / relative
                original = path.read_bytes()
                path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
                with patch.object(inputs, "_decompress", side_effect=AssertionError("must not parse")):
                    with self.assertRaisesRegex(ValueError, "source receipt"):
                        self.load(captured)

    def test_unreceipted_file_and_expanded_manifest_refused(self):
        captured = self.capture()
        (Path(captured["staging"]) / "unexpected.csv").write_text("invented\n")
        with self.assertRaisesRegex(ValueError, "unreceipted"):
            self.load(captured)
        captured = self.capture("expanded")
        manifest_path = Path(captured["manifest_path"])
        manifest = json.loads(manifest_path.read_bytes())
        manifest["profiles"].append(manifest["profiles"][0])
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Exactly four"):
            self.load(captured)

    def test_existing_staging_and_symlink_paths_refused(self):
        existing = self.root / "exists"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            inputs.fetch_public_inputs(existing)
        self.assertEqual((existing / "keep.txt").read_text(), "keep")
        captured = self.capture()
        alias = self.root / "alias"
        alias.symlink_to(captured["staging"], target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            inputs.load_study_inputs(alias)
        profile = Path(captured["staging"]) / inputs.PROFILE_PATHS[0]
        backup = self.root / "backup.gz"
        shutil.copyfile(profile, backup)
        profile.unlink()
        profile.symlink_to(backup)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.load(captured)

    def test_duplicate_profile_headers_rejected(self):
        original = inputs.PROFILE_PATHS[0]
        frame = self.frames[original]
        frame.columns = ["Cells_SYNTH" if x == "Cytoplasm_SYNTH" else x for x in frame]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.load(self.capture())

    def test_duplicate_source_headers_rejected(self):
        data = self.sources["experiment-metadata.tsv"]
        self.sources["experiment-metadata.tsv"] = data.replace(b"\tTime\t", b"\tDensity\t", 1)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.load(self.capture())

    def test_feature_schema_mismatch_rejected(self):
        frame = self.frames[inputs.PROFILE_PATHS[1]]
        self.frames[inputs.PROFILE_PATHS[1]] = frame[[*frame.columns[:-2], "Cytoplasm_SYNTH", "Cells_SYNTH"]]
        with self.assertRaisesRegex(ValueError, "ordered feature schema"):
            self.load(self.capture())

    def test_metadata_feature_audit_row_misalignment_rejected(self):
        captured = self.capture()
        validate = inputs.validate_a549_mapping
        def misalign(mapping):
            result = validate(mapping)
            result.loc[[0, 1], "audit_row"] = ["1", "0"]
            return result
        with patch.object(inputs, "validate_a549_mapping", side_effect=misalign):
            with self.assertRaisesRegex(ValueError, "alignment changed"):
                self.load(captured)

    def test_incomplete_or_wrong_plate_profile_rejected(self):
        path = inputs.PROFILE_PATHS[0]
        self.frames[path] = self.frames[path].iloc[:-1]
        with self.assertRaisesRegex(ValueError, "384"):
            self.load(self.capture())
        self.sources, self.frames = synthetic_tables()
        self.frames[path].loc[0, "Metadata_Plate"] = "SYNTH_OTHER_PLATE"
        with self.assertRaisesRegex(ValueError, "allowlisted plate"):
            self.load(self.capture("wrong-plate"))

    def test_wrong_condition_and_duplicate_physical_well_rejected(self):
        data = self.sources["experiment-metadata.tsv"]
        self.sources["experiment-metadata.tsv"] = data.replace(b"\t144\t", b"\t24\t")
        with self.assertRaisesRegex(ValueError, "144 h"):
            self.load(self.capture())
        self.sources, self.frames = synthetic_tables()
        self.frames[inputs.PROFILE_PATHS[0]].loc[1, "Metadata_Well"] = "A01"
        with self.assertRaisesRegex(ValueError, "Duplicate physical"):
            self.load(self.capture("duplicate-well"))

    def test_local_source_gene_and_sequence_disagreement_rejected(self):
        for column in ("Metadata_gene", "Metadata_target_sequence"):
            with self.subTest(column=column):
                self.sources, self.frames = synthetic_tables()
                self.frames[inputs.PROFILE_PATHS[0]].loc[31, column] = "SYNTH_CONFLICT"
                with self.assertRaises(ValueError):
                    self.load(self.capture(column))

    def test_ambiguous_reagent_source_join_rejected(self):
        name = "JUMP-Target-1_crispr_metadata.tsv"
        frame = pd.read_csv(io.BytesIO(self.sources[name]), sep="\t", dtype=str, keep_default_na=False)
        self.sources[name] = table_bytes(pd.concat([frame, frame.iloc[[0]]]), "\t")
        with self.assertRaisesRegex(ValueError, "ambiguous selected mappings"):
            self.load(self.capture())

    def test_sequence_aliases_retained_and_counted_without_biological_labels(self):
        name = "JUMP-Target-1_crispr_metadata.tsv"
        frame = pd.read_csv(io.BytesIO(self.sources[name]), sep="\t", dtype=str, keep_default_na=False)
        frame.loc[frame.broad_sample.eq("SYNTH_B"), "target_sequence"] = "ACGTAC"
        self.sources[name] = table_bytes(frame, "\t")
        for frame in self.frames.values():
            frame.loc[frame.Metadata_broad_sample.eq("SYNTH_B"), "Metadata_target_sequence"] = "ACGTAC"
        result = self.load(self.capture())
        self.assertEqual(result["receipt"]["source_sequences_shared_by_multiple_reagents"], 1)
        self.assertEqual(result["receipt"]["source_sequences_with_multiple_gene_strings"], 1)
        self.assertEqual(set(result["metadata"].loc[result["metadata"].treatment, "reagent"]), {"SYNTH_A", "SYNTH_B"})
        self.assertNotIn("reviewed", result["metadata"])

    def test_decompressed_limit_enforced(self):
        with patch.object(inputs, "MAX_DECOMPRESSED_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "decompressed"):
                inputs._decompress(gzip.compress(b"x" * 9))

    def test_gh_pinned_blob_verification_and_identity(self):
        path = inputs.PROFILE_PATHS[0]
        data = b"synthetic committed object\n"
        oid = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        info = json.dumps({"type": "file", "path": path, "sha": oid}).encode()
        with patch.object(inputs, "_bounded_process", side_effect=[info, data]) as request:
            self.assertEqual(inputs._gh_raw("/usr/bin/gh", path, 4096), data)
        first, second = request.call_args_list
        self.assertIn(f"repos/{inputs.REPO}/contents/{path}?ref={inputs.REVISION}", first.args[0])
        self.assertIn(f"repos/{inputs.REPO}/git/blobs/{oid}", second.args[0])
        with patch.object(inputs, "_bounded_process", side_effect=[info, data + b"corrupt"]):
            with self.assertRaisesRegex(ValueError, "Git blob SHA-1"):
                inputs._gh_raw("gh", path, 4096)

    def test_curl_fallback_keeps_tls_verification_and_fixed_url(self):
        url = inputs._media_url(inputs.PROFILE_PATHS[0])
        with patch.object(inputs, "_urllib_url", side_effect=urllib.error.URLError("synthetic certificate issue")), patch.object(inputs, "_bounded_process", return_value=b"data") as process:
            self.assertEqual(inputs._download_url(url, 123), b"data")
        arguments, bound = process.call_args.args
        self.assertEqual(arguments[1], "-q")
        self.assertIn("--proto", arguments)
        self.assertNotIn("--insecure", arguments)
        self.assertNotIn("--location", arguments)
        self.assertEqual(arguments[-1], url)
        self.assertEqual(bound, 123)

    def test_subprocess_stdout_bound_enforced(self):
        with self.assertRaisesRegex(ValueError, "byte bound"):
            inputs._bounded_process([sys.executable, "-c", "print('synthetic' * 1000)"], 16)

    def test_external_url_refused(self):
        with self.assertRaisesRegex(ValueError, "fixed public"):
            inputs._download_url("https://example.org/not-allowed", 100)


if __name__ == "__main__":
    unittest.main()
