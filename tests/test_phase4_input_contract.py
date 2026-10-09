"""Synthetic operator schema tests: NumPy is real, TIFF decoding is mocked.

These tests verify preparation decisions and output schemas, not TIFF-reader
compatibility, model execution, native approval checks or scientific results.
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comparator_tools as comparator


class NativeRecordIdTests(unittest.TestCase):
    def test_native_inventory_rejects_missing_value_markers(self):
        for value in ("nan", "NaN", "none", "NONE", "null", "NuLl", "<na>", "<NA>"):
            with self.subTest(record_id=value):
                with self.assertRaisesRegex(ValueError, "missing-value placeholders"):
                    comparator.validate_native_record_ids([value])

    def test_generic_ids_and_channel_names_keep_their_existing_contract(self):
        values = ["none", "NaN", "<NA>"]
        self.assertEqual(comparator.validate_ids(values), values)

    def test_native_ids_preserve_order_and_case(self):
        values = ["record-A", "record-a", "null-control"]
        self.assertEqual(comparator.validate_native_record_ids(values), values)

    def test_native_ids_keep_generic_validation(self):
        for values in ([], [None], [""], [" outer "], ["a\tb"], ["same", "same"]):
            with self.subTest(ids=values):
                with self.assertRaises(ValueError):
                    comparator.validate_native_record_ids(values)


class MockedTiffPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mocked-tiff-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.image = self.data / "fixture.tif"
        self.image.write_bytes(b"mocked TIFF fixture: this is not an encoded TIFF")
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps([{"record_id": "record-one", "path": "fixture.tif"}]))
        self.settings = self.root / "settings.json"

    def prepare_mocked_tiff(self, axes, height, width, *, channels=None):
        """The mock exposes header shape and decoded pixels; no decoder runs."""
        names = channels or ["channel-0", "channel-1", "channel-2"]
        self.settings.write_text(
            json.dumps(
                {
                    "axes": axes,
                    "preprocessing": {
                        "input_channels": names,
                        "model_channels": list(reversed(names)),
                        "input_range": [0, 255],
                        "mean": [0, 0, 0],
                        "std": [1, 1, 1],
                    },
                }
            )
        )
        shape = (3, height, width) if axes == "CYX" else (height, width, 3)
        series = types.SimpleNamespace(
            shape=shape,
            dtype=np.dtype("uint16"),
            axes=axes,
            asarray=mock.Mock(side_effect=lambda: np.ones(shape, dtype=np.uint16)),
        )
        fake = types.ModuleType("tifffile")
        fake.TiffFile = mock.Mock(
            side_effect=lambda path: contextlib.nullcontext(types.SimpleNamespace(series=[series]))
        )
        self.mocked_series = series
        with mock.patch.dict(sys.modules, {"tifffile": fake}):
            return comparator.prepare_images(
                self.selection, self.data, self.settings, self.root / "prepared"
            )

    def test_both_axis_orders_accept_the_native_minimum(self):
        for axes in ("CYX", "YXC"):
            with self.subTest(axes=axes):
                out = self.root / "prepared"
                if out.exists():
                    out.rename(self.root / "previous-prepared")
                report = self.prepare_mocked_tiff(axes, 8, 8)
                self.assertEqual(report["n_images"], 1)
                self.assertFalse(report["pixels_transformed"])
                inventory = json.loads((out / "image-inventory.json").read_text())
                self.assertEqual(
                    inventory,
                    [
                        {
                            "record_id": "record-one",
                            "path": "fixture.tif",
                            "sha256": comparator.digest(self.image),
                        }
                    ],
                )
                self.mocked_series.asarray.assert_called_once_with()

    def test_spatial_bounds_reject_before_mocked_decoding(self):
        for axes in ("CYX", "YXC"):
            for height, width in ((7, 8), (8, 7), (1025, 8), (8, 1025)):
                with self.subTest(axes=axes, height=height, width=width):
                    with self.assertRaisesRegex(ValueError, "Image/channel shape"):
                        self.prepare_mocked_tiff(axes, height, width)
                    self.mocked_series.asarray.assert_not_called()
                    self.assertFalse((self.root / "prepared").exists())

    def test_missing_record_id_does_not_publish_inventory(self):
        self.selection.write_text(json.dumps([{"record_id": "NaN", "path": "fixture.tif"}]))
        with self.assertRaisesRegex(ValueError, "missing-value placeholders"):
            self.prepare_mocked_tiff("CYX", 8, 8)
        self.mocked_series.asarray.assert_not_called()
        self.assertFalse((self.root / "prepared").exists())

    def test_channel_names_do_not_use_the_native_record_placeholder_rule(self):
        report = self.prepare_mocked_tiff("CYX", 8, 8, channels=["none", "NaN", "<NA>"])
        self.assertEqual(report["n_images"], 1)


if __name__ == "__main__":
    unittest.main()
