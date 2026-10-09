from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comparator_tools as c
import prepare_native_launch as n


def js(p, value):
    p.write_text(json.dumps(value))
    return p


def archive(p, x=None, ids=None):
    if x is None:
        x = np.array([[1, 0, 0], [0.8, 0.6, 0], [0, 0, 1]], dtype=np.float32)
    if ids is None:
        ids = np.array(["z", "a", "m"])
    np.savez(p, features=x, record_ids=ids)
    return p


@pytest.mark.parametrize("ids", [["a", "a"], ["", "b"], [" a", "b"], ["a\nb", "c"], [1, 2], []])
def test_bad_ids(ids):
    with pytest.raises(ValueError):
        c.validate_ids(ids)


def test_cosine():
    x = np.array([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
    sim, norm = c.cosine_matrix(x)
    assert np.allclose(np.diag(sim), 1.0)
    assert sim[0, 1] == 0.0
    assert sim[0, 2] == pytest.approx(1 / np.sqrt(2))
    assert np.allclose(norm, [1, 2, np.sqrt(2)])


def test_zero_norm():
    with pytest.raises(ValueError):
        c.cosine_matrix(np.zeros((2, 3)))


def test_no_self_and_stable_tie():
    x = np.ones((3, 2))
    sim, _ = c.cosine_matrix(x)
    nn, k = c.nearest_neighbors(sim, ["z", "a", "m"], 20)
    assert k == 2
    assert nn == [[1, 2], [2, 0], [1, 0]]


def test_headers(tmp_path):
    p = archive(tmp_path / "a.npz")
    h = c.npz_headers(p)
    assert h["features"]["shape"] == [3, 3]
    assert h["record_ids"]["kind"] == "U"


def test_object_arrays_rejected(tmp_path):
    p = archive(tmp_path / "a.npz", ids=np.array(["z", "a", "m"], dtype=object))
    with pytest.raises(ValueError, match="Object arrays"):
        c.npz_headers(p)


def test_info_cli_does_not_print_ids(tmp_path):
    p = archive(tmp_path / "a.npz", ids=np.array(["PRIVATE_ONE", "PRIVATE_TWO", "PRIVATE_THREE"]))
    r = subprocess.run(
        [sys.executable, c.__file__, "npz-info", str(p)], check=True, capture_output=True, text=True
    )
    assert "PRIVATE_ONE" not in r.stdout
    assert "record_ids" in r.stdout


@pytest.mark.parametrize(
    "change", ["nan", "inf", "zero", "bad_dim", "float64", "missing_key", "duplicate", "bad_count"]
)
def test_bad_analysis(tmp_path, change):
    x = np.eye(3, dtype=np.float32)
    ids = np.array(["z", "a", "m"])
    vkey, dim = "features", 3
    if change == "nan":
        x[0, 0] = np.nan
    if change == "inf":
        x[0, 0] = np.inf
    if change == "zero":
        x[0] = 0
    if change == "bad_dim":
        dim = 8
    if change == "float64":
        x = x.astype(np.float64)
    if change == "missing_key":
        vkey = "missing"
    if change == "duplicate":
        ids = np.array(["z", "a", "a"])
    if change == "bad_count":
        ids = np.array(["a", "b"])
    p = archive(tmp_path / "a.npz", x, ids)
    with pytest.raises(ValueError):
        c.analyze(p, vkey, "record_ids", tmp_path / "out", 2, dim, True, True)


def test_analyze_success(tmp_path):
    p = archive(tmp_path / "a.npz")
    h = c.digest(p)
    r = c.analyze(p, "features", "record_ids", tmp_path / "out", 2, 3, True, True)
    assert r["n_records"] == 3 and r["unit_norms_within_1e_5"]
    assert r["npz_sha256"] == h == c.digest(p)
    assert (tmp_path / "out" / "analysis-complete.json").is_file()
    text = (tmp_path / "out" / "neighbors.private.tsv").read_text().splitlines()
    assert len(text) == 7
    for row in text[1:]:
        a, b, *_ = row.split("\t")
        assert a != b
    assert "record_ids" not in r


def test_overwrite_rejected(tmp_path):
    p = archive(tmp_path / "a.npz")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(FileExistsError):
        c.analyze(p, "features", "record_ids", out, 2, 3, True, True)
    assert not list(out.iterdir())


def test_normalization_not_silently_claimed(tmp_path):
    p = archive(tmp_path / "a.npz", np.eye(3, dtype=np.float32) * 3)
    with pytest.raises(ValueError):
        c.analyze(p, "features", "record_ids", tmp_path / "bad", 2, 3, True, False)
    r = c.analyze(p, "features", "record_ids", tmp_path / "okay", 2, 3, False, False)
    assert not r["unit_norms_within_1e_5"]


def test_rank_ties():
    assert np.allclose(c.rank_average(np.array([9, 2, 2, 3])), [3, 0.5, 0.5, 2])


def test_compare_reorders_ids_and_different_dimensions(tmp_path):
    x = np.array([[1, 0, 0], [0.8, 0.6, 0], [0, 0, 1]], dtype=np.float32)
    left = archive(tmp_path / "a.npz", x)
    right = archive(
        tmp_path / "b.npz", np.pad(x[[2, 0, 1]], ((0, 0), (0, 2))), np.array(["m", "z", "a"])
    )
    r = c.compare(
        [["a", str(left), "features", "record_ids"], ["b", str(right), "features", "record_ids"]],
        "image",
        "test-contract",
        tmp_path / "out",
        1,
    )
    assert r["pairs"][0]["pairwise_cosine_spearman"] == pytest.approx(1)
    assert r["pairs"][0]["mean_neighbor_overlap_fraction"] == 1
    assert r["representations"][1]["reordered_by_record_id"]
    assert not r["cross_model_vector_dot_products"]


def test_compare_refuses_intersection(tmp_path):
    a = archive(tmp_path / "a.npz")
    b = archive(tmp_path / "b.npz", ids=np.array(["other", "a", "m"]))
    with pytest.raises(ValueError, match="identical ID"):
        c.compare(
            [["a", str(a), "features", "record_ids"], ["b", str(b), "features", "record_ids"]],
            "image",
            "x",
            tmp_path / "out",
            1,
        )


def test_compare_constant_no_fake_rho(tmp_path):
    a = archive(tmp_path / "a.npz", np.ones((3, 2)))
    b = archive(tmp_path / "b.npz", np.ones((3, 5)))
    r = c.compare(
        [["a", str(a), "features", "record_ids"], ["b", str(b), "features", "record_ids"]],
        "image",
        "x",
        tmp_path / "out",
        1,
    )
    assert r["pairs"][0]["pairwise_cosine_spearman"] is None
    assert r["pairs"][0]["undefined_reason"] == "constant_pairwise_similarity"


def scorefile(p, mode="good"):
    s = "method\tquery_id\tevaluable\taverage_precision\n"
    s += "a\tq1\ttrue\t0.8\na\tq2\tfalse\t\na\tq3\ttrue\t0.2\n"
    s += "b\tq3\ttrue\t0.1\nb\tq2\tfalse\t\nb\tq1\ttrue\t0.4\n"
    if mode == "zero":
        s = s.replace("false\t\n", "false\t0\n")
    if mode == "mask":
        s = s.replace("b\tq2\tfalse\t", "b\tq2\ttrue\t0.3")
    if mode == "nan":
        s = s.replace("true\t0.8", "true\tnan")
    if mode == "duplicate":
        s += "a\tq1\ttrue\t0.2\n"
    if mode == "population":
        s = s.replace("b\tq1", "b\tq4")
    if mode == "bool":
        s = s.replace("true", "maybe")
    if mode == "negative":
        s = s.replace("true\t0.8", "true\t-0.1")
    p.write_text(s)
    return p


def test_scores_summary(tmp_path):
    p = scorefile(tmp_path / "scores.tsv")
    r = c.scores_summary(
        p,
        tmp_path / "out",
        "method",
        "query_id",
        "evaluable",
        "average_precision",
        "contract",
        "\t",
    )
    assert r["coverage"] == pytest.approx(2 / 3)
    assert r["conditional_mean_by_method"] == {"a": 0.5, "b": 0.25}
    assert r["paired_mean_differences"][0]["mean_paired_difference_left_minus_right"] == 0.25


@pytest.mark.parametrize(
    "mode", ["zero", "mask", "nan", "duplicate", "population", "bool", "negative"]
)
def test_bad_scores(tmp_path, mode):
    p = scorefile(tmp_path / "scores.tsv", mode)
    with pytest.raises(ValueError):
        c.scores_summary(
            p,
            tmp_path / "out",
            "method",
            "query_id",
            "evaluable",
            "average_precision",
            "contract",
            "\t",
        )


def image_inputs(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    arr = np.arange(3 * 8 * 8, dtype=np.uint16).reshape(3, 8, 8)
    tifffile.imwrite(data / "a.tif", arr, photometric="minisblack", metadata={"axes": "CYX"})
    settings = js(
        tmp_path / "settings.json",
        {
            "axes": "CYX",
            "preprocessing": {
                "input_channels": ["c0", "c1", "c2"],
                "model_channels": ["c2", "c1", "c0"],
                "input_range": [0, 255],
                "mean": [0.5, 0.5, 0.5],
                "std": [0.2, 0.2, 0.2],
            },
        },
    )
    selection = js(tmp_path / "selection.json", [{"record_id": "r1", "path": "a.tif"}])
    return data, settings, selection


def test_image_inventory(tmp_path):
    data, settings, selection = image_inputs(tmp_path)
    h = c.digest(data / "a.tif")
    r = c.prepare_images(selection, data, settings, tmp_path / "out")
    assert r["n_images"] == 1 and not r["pixels_transformed"]
    inv = json.loads((tmp_path / "out" / "image-inventory.json").read_text())
    assert inv == [{"record_id": "r1", "path": "a.tif", "sha256": h}]
    assert c.digest(data / "a.tif") == h


@pytest.mark.parametrize(
    "mode", ["range", "channels", "axes", "std", "traversal", "absolute", "duplicate", "missing"]
)
def test_bad_images(tmp_path, mode):
    data, settings, selection = image_inputs(tmp_path)
    p = json.loads(settings.read_text())
    rows = json.loads(selection.read_text())
    if mode == "range":
        p["preprocessing"]["input_range"] = [0, 10]
    if mode == "channels":
        p["preprocessing"]["model_channels"] = ["c0", "c0", "c1"]
    if mode == "axes":
        p["axes"] = "XYZ"
    if mode == "std":
        p["preprocessing"]["std"] = [0, 1, 1]
    if mode == "traversal":
        rows[0]["path"] = "../a.tif"
    if mode == "absolute":
        rows[0]["path"] = str(data / "a.tif")
    if mode == "duplicate":
        rows.append(rows[0])
    if mode == "missing":
        rows[0]["path"] = "missing.tif"
    js(settings, p)
    js(selection, rows)
    with pytest.raises((ValueError, OSError)):
        c.prepare_images(selection, data, settings, tmp_path / "out")


def test_symlink_escape(tmp_path):
    data, settings, selection = image_inputs(tmp_path)
    outside = tmp_path / "outside.tif"
    outside.write_bytes((data / "a.tif").read_bytes())
    (data / "link.tif").symlink_to(outside)
    js(selection, [{"record_id": "r1", "path": "link.tif"}])
    with pytest.raises(ValueError):
        c.prepare_images(selection, data, settings, tmp_path / "out")


def test_native_request_does_not_accept_plan_only(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    asset = tmp_path / "assets"
    asset.mkdir()
    manifest = js(tmp_path / "m.json", {"model": "dinov2", "execution": "plan_only"})
    approval = js(data / "approval.json", {"source_commit": "a" * 40})
    request = js(
        tmp_path / "request.json",
        {
            "manifest": str(manifest),
            "approval": str(approval),
            "data_root": str(data),
            "asset_root": str(asset),
            "pilot_output": str(tmp_path / "run"),
        },
    )
    with pytest.raises(ValueError, match="approved_inference"):
        n.validate_request(request, code.resolve(), "a" * 40)


def test_native_request_null_paths(tmp_path):
    req = js(tmp_path / "request.json", {k: None for k in n.REQUEST_KEYS})
    with pytest.raises(ValueError, match="UNRESOLVED"):
        n.validate_request(req, tmp_path / "code", "a" * 40)


def test_bound_inventory_escape(tmp_path):
    with pytest.raises(ValueError):
        n.confined_inventory(tmp_path, "../data.json")


def test_launcher_requires_explicit_authorization(tmp_path):
    import os

    script = Path(c.__file__).resolve().parents[1] / "slurm/run_dinov2_once.sbatch"
    env = os.environ.copy()
    env["SLURM_JOB_ID"] = "test-only"
    env.pop("SLURM_ARRAY_JOB_ID", None)
    r = subprocess.run(["bash", str(script), "unused"], env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "explicit operator authorization" in r.stdout


def test_cli_help():
    for module in (c, n):
        p = subprocess.run(
            [sys.executable, module.__file__, "--help"], capture_output=True, text=True
        )
        assert p.returncode == 0


def test_auto_keys(tmp_path):
    p = archive(tmp_path / "a.npz")
    r = c.analyze(p, "auto", "auto", tmp_path / "out", 2, 3, True, True)
    assert r["npz_vector_key"] == "features" and r["npz_id_key"] == "record_ids"


def test_ambiguous_feature_auto_rejected(tmp_path):
    p = tmp_path / "a.npz"
    np.savez(p, first=np.eye(3), second=np.eye(3), ids=np.array(["a", "b", "c"]))
    with pytest.raises(ValueError, match="ambiguous"):
        c.load_vectors(p, "auto", "auto")


def test_ambiguous_ids_auto_rejected(tmp_path):
    p = tmp_path / "a.npz"
    np.savez(p, vectors=np.eye(3), ids=np.array(["a", "b", "c"]), other=np.array(["a", "b", "c"]))
    with pytest.raises(ValueError, match="ambiguous"):
        c.load_vectors(p, "auto", "auto")


def test_scores_column_roles_distinct(tmp_path):
    p = scorefile(tmp_path / "scores.tsv")
    with pytest.raises(ValueError, match="distinct"):
        c.scores_summary(
            p, tmp_path / "out", "method", "method", "evaluable", "average_precision", "x", "\t"
        )
