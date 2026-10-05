"""Synthetic end-to-end checks of the installed image workflow boundaries."""

import csv
import json

import numpy as np
import pytest
from sklearn.metrics import pairwise_distances
from tifffile import TiffWriter, imread, imwrite
from typer.testing import CliRunner

from perturb_lm.cli.main import app
from perturb_lm.images.pixel_analyzer import PixelMorphologyTransformer, read_tiff_chw
from perturb_lm.images.pixel_state import (
    checksum,
    load_index,
    load_preprocessor,
    read_record,
    state_payload,
)
from perturb_lm.images.pixel_workflow import run_images


def pixels(radius=4):
    yy, xx = np.mgrid[:64, :64]
    signal = np.zeros((64, 64), dtype=np.uint16)
    for y, x in ((16, 16), (16, 46), (46, 16), (46, 46)):
        signal[(yy - y) ** 2 + (xx - x) ** 2 <= radius**2] = 2000
    return np.stack([signal, signal // 2])


def tiff(path, image):
    imwrite(path, image, photometric="minisblack")
    return path


def rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def reference(tmp_path):
    paths = [tiff(tmp_path / f"r{i}.tif", pixels(r)) for i, r in enumerate((3, 5, 7))]
    output = tmp_path / "reference"
    run_images(
        paths,
        output=output,
        axes="CYX",
        channels=["c0", "c1"],
        mode="fit",
        image_ids=["ref-a", "ref-b", "ref-c"],
    )
    return output, paths


def test_standalone_analysis_has_objects_masks_and_units_without_fitting(tmp_path):
    path = tiff(tmp_path / "anything.tif", pixels())
    out = tmp_path / "analysis"
    result = run_images([path], output=out, axes="CYX", channels=["c0", "c1"])
    assert result["n_accepted"] == 1
    assert not result["scaled_features"]
    assert not (out / "state.json").exists() and not (out / "scaled_features.csv").exists()
    mask = imread(out / "masks/000000.tif")
    measurements = rows(out / "measurements.csv")
    assert mask.max() == len(measurements) == 4
    for obj in measurements:
        object_pixels = mask == int(obj["object_id"])
        assert int(float(obj["area_px2"])) == int(object_pixels.sum())
        assert float(obj["channel_0_sum_intensity"]) == pixels()[0][object_pixels].sum()
    units = json.loads((out / "units.json").read_text())
    assert units["measurements"]["area_px2"] == "pixel^2"
    assert units["features"]["object_area_mean_px"] == "pixel^2"
    assert "Object boundaries" in (out / "report.html").read_text()


def test_renamed_decoded_tiffs_produce_identical_features_and_distances(reference, tmp_path):
    folder, paths = reference
    renamed = tiff(tmp_path / "other_label_other_plate.tif", imread(paths[1]))
    run_images(
        [renamed, paths[1]],
        output=tmp_path / "queries",
        axes="CYX",
        channels=["c0", "c1"],
        mode="search",
        reference=folder,
        image_ids=["query-a", "query-b"],
        top_k=3,
    )
    features = rows(tmp_path / "queries/raw_features.csv")
    assert {k: v for k, v in features[0].items() if k != "image_id"} == {
        k: v for k, v in features[1].items() if k != "image_id"
    }
    neighbors = rows(tmp_path / "queries/neighbors.csv")
    assert [r["distance"] for r in neighbors[:3]] == [r["distance"] for r in neighbors[3:]]
    assert neighbors[0]["reference_id"] == "ref-b"
    assert [r["query_id"] for r in neighbors] == ["query-a"] * 3 + ["query-b"] * 3


def test_external_labels_and_ids_cannot_change_features_or_distances(tmp_path):
    images = [pixels(3), pixels(5), pixels(7)]
    a = PixelMorphologyTransformer().fit(images, ["gene_A", "plate_1", "compound_x"])
    b = PixelMorphologyTransformer().fit(images, ["unrelated", "labels", "changed"])
    np.testing.assert_array_equal(a.transform(images), b.transform(images))
    np.testing.assert_array_equal(
        pairwise_distances(a.transform(images)), pairwise_distances(b.transform(images))
    )
    paths = [tiff(tmp_path / f"{i}.tif", image) for i, image in enumerate(images)]
    for name, ids in (("a", ["first", "second", "third"]), ("b", ["x", "y", "z"])):
        run_images(
            paths,
            output=tmp_path / name,
            axes="CYX",
            channels=["c0", "c1"],
            mode="fit",
            image_ids=ids,
        )
    left, right = (read_record(tmp_path / name / "index.json") for name in ("a", "b"))
    assert left["raw"] == right["raw"] and left["scaled"] == right["scaled"]
    np.testing.assert_array_equal(
        pairwise_distances(left["scaled"]), pairwise_distances(right["scaled"])
    )


def test_controlled_pixel_changes_have_expected_measurement_effects():
    model = PixelMorphologyTransformer()
    small, _, objects_small = model.measure(pixels(3))
    large, _, objects_large = model.measure(pixels(7))
    brighter, _, objects_bright = model.measure(pixels(3) * 2)
    assert sum(r["area_px2"] for r in objects_large) > sum(r["area_px2"] for r in objects_small)
    names = model._names(2).tolist()
    assert large[names.index("foreground_fraction")] > small[names.index("foreground_fraction")]
    assert brighter[names.index("channel_0_mean")] == pytest.approx(
        2 * small[names.index("channel_0_mean")]
    )
    assert [r["area_px2"] for r in objects_bright] == [r["area_px2"] for r in objects_small]
    assert brighter[0] == small[0] == large[0] == 4


def test_reference_only_fit_persistence_and_inference_immutability(reference, tmp_path):
    folder, paths = reference
    before = {p.name: p.read_bytes() for p in (folder / "state.json", folder / "index.json")}
    model, state, index = load_index(folder, channels=["c0", "c1"])
    np.testing.assert_allclose(model.scaler_.mean_, np.asarray(index["raw"]).mean(axis=0))
    snapshot = checksum(state_payload(model, ["c0", "c1"]))
    queries = [pixels(9) * 2]
    expected = model.transform(queries)
    assert checksum(state_payload(model, ["c0", "c1"])) == snapshot
    query = tiff(tmp_path / "query.tif", queries[0])
    for mode in ("search", "analyze"):
        kwargs = {"reference": folder} if mode == "search" else {"state": folder / "state.json"}
        run_images(
            [query], output=tmp_path / mode, mode=mode, axes="CYX", channels=["c0", "c1"], **kwargs
        )
        table = rows(tmp_path / mode / "scaled_features.csv")
        np.testing.assert_allclose(
            [[float(table[0][name]) for name in state["features"]]], expected
        )
    assert before == {
        p.name: p.read_bytes() for p in (folder / "state.json", folder / "index.json")
    }


def test_mixed_qc_is_explicit_and_invalid_inputs_never_become_feature_rows(tmp_path):
    good = tiff(tmp_path / "good.tif", pixels())
    blank = tiff(tmp_path / "blank.tif", np.zeros_like(pixels()))
    nonfinite = pixels().astype(float)
    nonfinite[0, 0, 0] = np.nan
    nan = tiff(tmp_path / "nan.tif", nonfinite)
    wrong = tiff(tmp_path / "wrong.tif", pixels()[:1])
    corrupt = tmp_path / "bad.tif"
    corrupt.write_bytes(b"not a tiff")
    result = run_images(
        [good, blank, nan, wrong, corrupt],
        output=tmp_path / "out",
        axes="CYX",
        channels=["c0", "c1"],
        mode="fit",
    )
    assert result["n_accepted"] == 1 and result["n_excluded"] == 4
    qc = rows(tmp_path / "out/qc.csv")
    assert {r["reason"] for r in qc[1:]} == {
        "blank",
        "nonfinite_or_nonnumeric",
        "incompatible_channels",
        "unreadable",
    }
    assert len(rows(tmp_path / "out/raw_features.csv")) == 1
    assert len(read_record(tmp_path / "out/index.json")["rows"]) == 1
    assert read_record(tmp_path / "out/state.json")["scaler"]["n_samples"] == 1


def test_blank_unused_channel_does_not_override_explicit_segmentation_choice(tmp_path):
    image = pixels()
    image[0] = 0
    source = tiff(tmp_path / "image.tif", image)
    result = run_images(
        [source],
        output=tmp_path / "out",
        axes="CYX",
        channels=["empty", "signal"],
        segmentation_channel=1,
    )
    assert result["n_accepted"] == 1


def test_all_invalid_outputs_report_failure_without_fitted_artifacts(tmp_path):
    source = tiff(tmp_path / "blank.tif", np.zeros_like(pixels()))
    out = tmp_path / "none"
    result = run_images([source], output=out, axes="CYX", channels=["c0", "c1"], mode="fit")
    assert result["status"] == "no_valid_images"
    assert (out / "report.html").is_file() and not (out / "state.json").exists()
    assert not (out / "index.json").exists()
    assert rows(out / "raw_features.csv") == []


@pytest.mark.parametrize(
    "mutation", ["checksum", "schema", "feature_names", "negative_scale", "channels"]
)
def test_corrupt_or_incompatible_preprocessing_fails(reference, tmp_path, mutation):
    folder, _ = reference
    envelope = json.loads((folder / "state.json").read_text())
    if mutation == "checksum":
        envelope["payload"]["scaler"]["mean"][0] += 1
    elif mutation == "schema":
        envelope["payload"]["feature_schema"] = "future-schema"
    elif mutation == "feature_names":
        envelope["payload"]["features"][0] = "unknown_feature"
    elif mutation == "negative_scale":
        envelope["payload"]["scaler"]["scale"][0] = -1
    elif mutation == "channels":
        envelope["payload"]["channels"].reverse()
    if mutation != "checksum":
        envelope["sha256"] = checksum(envelope["payload"])
    bad = tmp_path / "state.json"
    bad.write_text(json.dumps(envelope))
    with pytest.raises(ValueError):
        load_preprocessor(bad, channels=["c0", "c1"])


def test_index_corruption_or_mismatched_rows_fail(reference):
    folder, _ = reference
    envelope = json.loads((folder / "index.json").read_text())
    envelope["payload"]["rows"][0]["image_id"] = envelope["payload"]["rows"][1]["image_id"]
    envelope["sha256"] = checksum(envelope["payload"])
    (folder / "index.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="identities"):
        load_index(folder, channels=["c0", "c1"])


def test_axes_series_and_channel_order_are_explicit(reference, tmp_path):
    folder, _ = reference
    with pytest.raises(ValueError, match="channels"):
        load_index(folder, channels=["c1", "c0"])
    path = tmp_path / "multi.tif"
    with TiffWriter(path) as writer:
        writer.write(pixels(), photometric="minisblack")
        writer.write(pixels(6), photometric="minisblack")
    with pytest.raises(ValueError, match="multiple series"):
        read_tiff_chw(path, axes="CYX")
    np.testing.assert_array_equal(read_tiff_chw(path, axes="CYX", series=1), pixels(6))
    with pytest.raises(ValueError, match="axes"):
        read_tiff_chw(path, axes="YX", series=0)


def test_yxc_and_cyx_decode_to_same_features(tmp_path):
    a = tiff(tmp_path / "cyx.tif", pixels())
    b = tiff(tmp_path / "yxc.tif", np.moveaxis(pixels(), 0, -1))
    model = PixelMorphologyTransformer().fit([read_tiff_chw(a, axes="CYX")])
    np.testing.assert_array_equal(
        model.raw_features([read_tiff_chw(a, axes="CYX")]),
        model.raw_features([read_tiff_chw(b, axes="YXC")]),
    )


def test_cli_exit_codes_reports_and_escaped_ids(tmp_path):
    runner = CliRunner()
    good = tiff(tmp_path / "good.tif", pixels())
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"broken")
    result = runner.invoke(
        app,
        [
            "images",
            "analyze",
            str(good),
            str(bad),
            "--axes",
            "CYX",
            "--channels",
            "c0,c1",
            "--out",
            str(tmp_path / "mixed"),
            "--image-id",
            "<script>alert(1)</script>",
            "--image-id",
            "bad",
        ],
    )
    assert result.exit_code == 1, result.output
    report = (tmp_path / "mixed/report.html").read_text()
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;" in report
    only_bad = runner.invoke(
        app,
        [
            "images",
            "fit",
            str(bad),
            "--axes",
            "CYX",
            "--channels",
            "c0,c1",
            "--out",
            str(tmp_path / "invalid"),
        ],
    )
    assert only_bad.exit_code == 2
    missing_axes = runner.invoke(
        app,
        ["images", "analyze", str(good), "--channels", "c0,c1", "--out", str(tmp_path / "missing")],
    )
    assert missing_axes.exit_code == 2
    success = runner.invoke(
        app,
        [
            "images",
            "analyze",
            str(good),
            "--axes",
            "CYX",
            "--channels",
            "c0,c1",
            "--out",
            str(tmp_path / "success"),
        ],
    )
    assert success.exit_code == 0, success.output
    assert runner.invoke(app, ["version"]).exit_code == 0


def test_output_is_not_overwritten_and_duplicate_ids_are_rejected(tmp_path):
    path = tiff(tmp_path / "good.tif", pixels())
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(FileExistsError):
        run_images([path], output=out, axes="CYX", channels=["c0", "c1"])
    with pytest.raises(ValueError, match="unique"):
        run_images(
            [path, path],
            output=tmp_path / "duplicate",
            axes="CYX",
            channels=["c0", "c1"],
            image_ids=["same", "same"],
        )
