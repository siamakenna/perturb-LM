#!/usr/bin/env python3
"""Offline input preparation and descriptive comparator analysis.

No model loader, downloader, scheduler, alignment trainer, or approval issuer.
Use the repository's reviewed pilot worker for pretrained inference.
All outputs are private by default and refuse existing output directories.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

VERSION = "1.0.2"
MAX_NPZ_BYTES = 512 * 1024 * 1024
MAX_MATRIX_ELEMENTS = 10_000_000
MAX_ANALYSIS_ROWS = 2048
MAX_INPUT_BYTES = 32 * 1024 * 1024


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("JSON exceeds the 16 MiB preparation limit")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Any) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def new_output(path: Path) -> Path:
    if path.exists():
        raise FileExistsError("Output already exists; preserve it and select a new output directory")
    path.mkdir(mode=0o700, parents=False)
    return path


def finish(out: Path, report: dict[str, Any]) -> dict[str, Any]:
    report = {"tool_version": VERSION, "tool_sha256": digest(Path(__file__)), **report}
    write_json(out / "summary.json", report)
    files = {p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    write_json(out / "analysis-complete.json", {
        "scope": "operator_analysis_not_native_pilot_completion",
        "files_sha256": files,
    })
    return report


def validate_ids(values: list[Any]) -> list[str]:
    if not values or any(not isinstance(x, str) or not x or x != x.strip() for x in values):
        raise ValueError("Record IDs must be explicit nonempty strings without outer whitespace")
    if any(any(ord(c) < 32 for c in x) for x in values):
        raise ValueError("Record IDs may not contain control characters")
    if len(set(values)) != len(values):
        raise ValueError("Duplicate record IDs; do not silently aggregate or deduplicate")
    return values


def validate_native_record_ids(values: list[Any]) -> list[str]:
    """Apply the native pilot's missing-value rule to inventory record IDs only."""
    ids = validate_ids(values)
    if any(value.lower() in {"nan", "none", "null", "<na>"} for value in ids):
        raise ValueError("Native record IDs may not use missing-value placeholders")
    return ids


def ids_digest(ids: list[str]) -> str:
    return hashlib.sha256(json.dumps(ids, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def confined_file(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("Image path must be a relative path with no parent traversal")
    path = (root / rel).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Image path escapes the selected root or is not a regular file")
    if path.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Only numeric TIFF inputs are supported")
    return path


def prepare_images(selection: Path, root: Path, settings: Path, out: Path) -> dict[str, Any]:
    """Create the native record_id/path/sha256 inventory; never modify pixels."""
    import numpy as np
    import tifffile

    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Data root must be a directory")
    rows, image = read_json(selection), read_json(settings)
    selection_hash, settings_hash = digest(selection), digest(settings)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValueError("Select between one and eight actual input records")
    if any(not isinstance(r, dict) or set(r) != {"record_id", "path"} for r in rows):
        raise ValueError("Selection rows must have exactly record_id and path")
    ids = validate_native_record_ids([r["record_id"] for r in rows])
    if not isinstance(image, dict) or set(image) != {"axes", "preprocessing"}:
        raise ValueError("Image settings require axes and preprocessing only")
    axes = image["axes"]
    if axes not in {"CYX", "YXC"}:
        raise ValueError("Declare CYX or YXC axes; no axis/channel guessing")
    p = image["preprocessing"]
    required = {"input_channels", "model_channels", "input_range", "mean", "std"}
    if not isinstance(p, dict) or set(p) != required:
        raise ValueError("Preprocessing settings incomplete or contain unknown fields")
    channels, chosen = p["input_channels"], p["model_channels"]
    if not isinstance(channels, list) or not 3 <= len(channels) <= 8:
        raise ValueError("Explicit three-to-eight input channel names are required")
    validate_ids(channels)
    if not isinstance(chosen, list) or len(chosen) != 3:
        raise ValueError("Exactly three ordered model channels are required")
    validate_ids(chosen)
    if not set(chosen).issubset(channels):
        raise ValueError("Model channel not present in input channels")
    for field, length in (("input_range", 2), ("mean", 3), ("std", 3)):
        seq = p[field]
        if not isinstance(seq, list) or len(seq) != length or any(type(v) not in (int, float) or not math.isfinite(v) for v in seq):
            raise ValueError(f"Invalid finite numeric values for {field}")
    low, high = p["input_range"]
    if high <= low or any(s <= 0 for s in p["std"]):
        raise ValueError("Invalid fixed range or standard deviations")

    inventory, technical, before = [], [], []
    shape = None
    observed_paths = set()
    for index, row in enumerate(rows):
        path = confined_file(root, row["path"])
        if path in observed_paths:
            raise ValueError("The same image file was selected twice")
        observed_paths.add(path)
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("Selected file exceeds the 32 MiB first-pilot limit")
        h = digest(path)
        with tifffile.TiffFile(path) as tf:
            if len(tf.series) != 1:
                raise ValueError("Ambiguous multi-series TIFF; provide a reviewed single-series input")
            s = tf.series[0]
            if len(s.shape) != 3 or np.dtype(s.dtype).kind not in "uif":
                raise ValueError("Require a real numeric three-dimensional TIFF; do not auto-stack channels")
            dims = dict(zip(axes, s.shape))
            if dims["C"] != len(channels) or not 8 <= dims["Y"] <= 1024 or not 8 <= dims["X"] <= 1024:
                raise ValueError("Image/channel shape violates the declared pilot contract")
            if math.prod(s.shape) * np.dtype(s.dtype).itemsize > 64 * 1024 * 1024:
                raise ValueError("Decoded input exceeds this preparation tool's 64 MiB bound")
            arr = s.asarray()
            reported_axes = s.axes
        if shape is not None and tuple(arr.shape) != shape:
            raise ValueError("Selected inputs do not have uniform dimensions")
        shape = tuple(arr.shape)
        if not np.isfinite(arr).all():
            raise ValueError("Nonfinite image pixels")
        amin, amax = float(np.min(arr)), float(np.max(arr))
        if amin < low or amax > high:
            raise ValueError("Pixels outside the declared fixed intensity range; no clipping was performed")
        if digest(path) != h:
            raise ValueError("Image changed while being inspected")
        before.append((path, h))
        inventory.append({"record_id": row["record_id"], "path": row["path"], "sha256": h})
        technical.append({"record_id": row["record_id"], "reported_tiff_axes": reported_axes,
                          "declared_axes": axes, "shape": list(shape), "dtype": str(arr.dtype),
                          "minimum": amin, "maximum": amax, "constant_pixels": amin == amax})
    if digest(selection) != selection_hash or digest(settings) != settings_hash or any(digest(pth) != h for pth, h in before):
        raise ValueError("A preparation input changed")
    new_output(out)
    write_json(out / "image-inventory.json", inventory)
    write_json(out / "image-settings.json", image)
    write_json(out / "input-qc.private.json", technical)
    report = {
        "scope": "DINOv2_input_preparation_not_approval", "n_images": len(rows),
        "axes": axes, "uniform_shape": list(shape), "record_order_sha256": ids_digest(ids),
        "image_inventory_sha256": digest(out / "image-inventory.json"),
        "image_settings_sha256": digest(out / "image-settings.json"),
        "constant_image_count": sum(r["constant_pixels"] for r in technical),
        "pixels_transformed": False, "pretrained_inference_performed": False,
        "ready_for_pretrained_submission": False,
        "channel_semantics": "operator_declared_not_inferred_or_verified",
    }
    return finish(out, report)


def npz_headers(path: Path) -> dict[str, dict[str, Any]]:
    """Read only NPY headers, reject object dtypes and oversized archive payloads."""
    import numpy as np
    if path.stat().st_size > MAX_NPZ_BYTES:
        raise ValueError("NPZ exceeds the bounded analysis limit")
    headers = {}
    with zipfile.ZipFile(path) as z:
        info = z.infolist()
        if len(info) > 64 or sum(v.file_size for v in info) > MAX_NPZ_BYTES:
            raise ValueError("Uncompressed archive exceeds the bounded analysis limit")
        for member in info:
            if not member.filename.endswith(".npy") or "/" in member.filename or "\\" in member.filename:
                raise ValueError("Unexpected NPZ member")
            key = member.filename[:-4]
            if key in headers:
                raise ValueError("Duplicate archive key")
            with z.open(member) as f:
                v = np.lib.format.read_magic(f)
                if v == (1, 0):
                    shape, order, dtype = np.lib.format.read_array_header_1_0(f)
                elif v == (2, 0):
                    shape, order, dtype = np.lib.format.read_array_header_2_0(f)
                else:
                    raise ValueError("Unsupported NPY header version; export ordinary numeric/string arrays")
            if dtype.hasobject:
                raise ValueError("Object arrays are not accepted; export Unicode IDs and numeric vectors without pickle")
            size = math.prod(shape) * dtype.itemsize
            if size > MAX_NPZ_BYTES or size > member.file_size:
                raise ValueError("Implausible or oversized NPY payload")
            headers[key] = {"shape": list(shape), "dtype": str(dtype), "kind": dtype.kind}
    return headers


def resolve_keys(headers: dict[str, dict[str, Any]], vector_key: str, id_key: str) -> tuple[str, str]:
    if vector_key == "auto":
        choices = [key for key, h in headers.items() if len(h["shape"]) == 2 and h["kind"] in "fiu"]
        if len(choices) != 1:
            raise ValueError("Feature key is ambiguous; use npz-info and supply --vectors-key")
        vector_key = choices[0]
    if vector_key not in headers or len(headers[vector_key]["shape"]) != 2:
        raise ValueError("Requested feature matrix is absent")
    if id_key == "auto":
        n = headers[vector_key]["shape"][0]
        choices = [key for key, h in headers.items() if h["shape"] == [n] and h["kind"] in "SU"]
        if len(choices) != 1:
            raise ValueError("ID key is ambiguous; use npz-info and supply --ids-key")
        id_key = choices[0]
    return vector_key, id_key


def load_vectors(path: Path, vector_key: str, id_key: str) -> tuple[Any, list[str], str, str]:
    import numpy as np
    before = digest(path)
    headers = npz_headers(path)
    vector_key, id_key = resolve_keys(headers, vector_key, id_key)
    if vector_key not in headers or id_key not in headers:
        raise ValueError("Requested NPZ keys absent; run npz-info and use the actual keys")
    h = headers[vector_key]
    shape = h["shape"]
    if len(shape) != 2 or not 2 <= shape[0] <= MAX_ANALYSIS_ROWS or shape[1] < 1 or math.prod(shape) > MAX_MATRIX_ELEMENTS or h["kind"] not in "fiu":
        raise ValueError("Expected a bounded two-dimensional real numeric feature array, with at least two rows")
    ih = headers[id_key]
    if ih["shape"] != [shape[0]] or ih["kind"] not in "SU":
        raise ValueError("IDs must be a one-dimensional Unicode/bytes array with one ID per feature row")
    with np.load(path, allow_pickle=False) as data:
        original = data[vector_key]
        original_dtype = str(original.dtype)
        if original.dtype.kind in "iu" and (
            int(original.min()) < -(2**53) or int(original.max()) > 2**53
        ):
            raise ValueError("Integer feature values outside [-2**53, 2**53] risk precision loss when converted to float64")
        x = np.asarray(original, dtype=np.float64)
        raw_ids = data[id_key].tolist()
        ids = validate_ids([v.decode("utf-8") if isinstance(v, bytes) else v for v in raw_ids])
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite feature value; no imputation is performed")
    if digest(path) != before:
        raise ValueError("NPZ changed while reading")
    return x, ids, before, original_dtype


def cosine_matrix(x: Any) -> tuple[Any, Any]:
    import numpy as np
    norms = np.linalg.norm(x, axis=1)
    if not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError("Nonfinite or zero feature norm; cannot compute valid cosine similarity")
    unit = x / norms[:, None]
    return np.clip(unit @ unit.T, -1.0, 1.0), norms


def nearest_neighbors(sim: Any, ids: list[str], k: int) -> tuple[list[list[int]], int]:
    import numpy as np
    if k < 1:
        raise ValueError("k must be positive")
    k = min(k, len(ids) - 1)
    names = np.asarray(ids)
    neighbors = []
    for i in range(len(ids)):
        candidates = np.arange(len(ids)) != i
        ix = np.flatnonzero(candidates)
        order = np.lexsort((names[ix], -sim[i, ix]))
        neighbors.append(ix[order[:k]].tolist())
    return neighbors, k


def analyze(path: Path, vectors: str, ids_key: str, out: Path, k: int, expected_dim: int | None,
            require_unit: bool, require_float32: bool) -> dict[str, Any]:
    import numpy as np
    vectors, ids_key = resolve_keys(npz_headers(path), vectors, ids_key)
    x, ids, h, dtype = load_vectors(path, vectors, ids_key)
    if expected_dim is not None and x.shape[1] != expected_dim:
        raise ValueError("Feature dimension differs from the expected encoder contract")
    if require_float32 and dtype != "float32":
        raise ValueError("Expected original float32 feature output")
    sim, norms = cosine_matrix(x)
    unit_ok = bool(np.allclose(norms, 1.0, atol=1e-5, rtol=0))
    if require_unit and not unit_ok:
        raise ValueError("Expected L2-normalized output; no repair or silent renormalization of source file")
    neighbors, k = nearest_neighbors(sim, ids, k)
    upper = sim[np.triu_indices(len(ids), 1)]
    variance = np.var(x, axis=0)
    report = {
        "scope": "descriptive_feature_geometry_not_retrieval_accuracy", "npz_sha256": h,
        "npz_vector_key": vectors, "npz_id_key": ids_key, "n_records": len(ids),
        "dimension": x.shape[1], "stored_dtype": dtype, "all_finite": True,
        "unit_norms_within_1e_5": unit_ok, "norm_min": float(norms.min()),
        "norm_max": float(norms.max()), "record_order_sha256": ids_digest(ids),
        "exact_duplicate_vector_rows": len(x) - int(np.unique(x, axis=0).shape[0]),
        "constant_dimensions": int(np.count_nonzero(variance == 0)),
        "off_diagonal_cosine_mean": float(upper.mean()),
        "off_diagonal_cosine_min": float(upper.min()),
        "off_diagonal_cosine_max": float(upper.max()),
        "near_identical_pairs_cosine_ge_0_999999": int(np.count_nonzero(upper >= 0.999999)),
        "k": k, "excluded": "identical_record_id_only", "tie_rule": "ascending_record_id",
        "labels_used": False, "treatment_or_plate_filters_applied": False,
        "input_approval_verified": False, "native_completion_verified": False,
        "warning": "Neighbors are exploratory; no relevance labels, AP, mAP, CIs, or claims of generalization",
    }
    new_output(out)
    with (out / "neighbors.private.tsv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["query_id", "candidate_id", "rank", "cosine_similarity"])
        for i, choices in enumerate(neighbors):
            for rank, j in enumerate(choices, 1):
                writer.writerow([ids[i], ids[j], rank, format(float(sim[i, j]), ".17g")])
    np.savez_compressed(out / "cosine.private.npz", cosine=sim, record_ids=np.asarray(ids))
    if digest(path) != h:
        raise ValueError("Feature archive changed during analysis")
    return finish(out, report)


def rank_average(values: Any) -> Any:
    import numpy as np
    order = np.argsort(values, kind="stable")
    ranked = np.empty(len(values), dtype=float)
    left = 0
    while left < len(order):
        right = left + 1
        while right < len(order) and values[order[right]] == values[order[left]]:
            right += 1
        ranked[order[left:right]] = (left + right - 1) / 2.0
        left = right
    return ranked


def compare(representations: list[list[str]], unit: str, condition: str, out: Path, k: int) -> dict[str, Any]:
    import numpy as np
    if not 2 <= len(representations) <= 10:
        raise ValueError("Compare two through ten completed representations")
    names = [r[0] for r in representations]
    validate_ids(names)
    all_models, reference_ids, sources = {}, None, []
    for name, filename, vkey, ikey in representations:
        path = Path(filename)
        vkey, ikey = resolve_keys(npz_headers(path), vkey, ikey)
        x, ids, h, dtype = load_vectors(path, vkey, ikey)
        if reference_ids is None:
            reference_ids = ids
        if set(ids) != set(reference_ids):
            raise ValueError("Representations do not have identical ID populations; no silent intersection")
        order_changed = ids != reference_ids
        lookup = {v: i for i, v in enumerate(ids)}
        x = x[[lookup[v] for v in reference_ids]]
        sim, _ = cosine_matrix(x)
        nn, actual_k = nearest_neighbors(sim, reference_ids, k)
        all_models[name] = {"sim": sim, "neighbors": nn}
        sources.append({"name": name, "npz_sha256": h, "dimension": x.shape[1],
                        "stored_dtype": dtype, "reordered_by_record_id": order_changed,
                        "vectors_key": vkey, "ids_key": ikey})
    assert reference_ids is not None
    triangle = np.triu_indices(len(reference_ids), 1)
    pairs = []
    for a, b in itertools.combinations(names, 2):
        av, bv = all_models[a]["sim"][triangle], all_models[b]["sim"][triangle]
        ra, rb = rank_average(av), rank_average(bv)
        if np.ptp(ra) == 0 or np.ptp(rb) == 0:
            rho, reason = None, "constant_pairwise_similarity"
        else:
            rho, reason = float(np.corrcoef(ra, rb)[0, 1]), None
        overlaps = [len(set(left) & set(right)) / actual_k
                    for left, right in zip(all_models[a]["neighbors"], all_models[b]["neighbors"])]
        pairs.append({"left": a, "right": b, "pairwise_cosine_spearman": rho,
                      "undefined_reason": reason, "mean_neighbor_overlap_fraction": float(np.mean(overlaps)),
                      "k": actual_k})
    for (_, filename, _, _), src in zip(representations, sources):
        if digest(Path(filename)) != src["npz_sha256"]:
            raise ValueError("Input representation changed during comparison")
    report = {"scope": "descriptive_same_record_geometry_comparison", "unit": unit,
              "condition_label": condition, "condition_and_unit": "operator_declared_not_independently_verified",
              "n_records": len(reference_ids), "record_order_sha256": ids_digest(reference_ids),
              "representations": sources, "pairs": pairs, "cross_model_vector_dot_products": False,
              "p_values_or_confidence_intervals_computed": False,
              "warning": "Dependent pairwise distances are not independent observations; agreement is not accuracy. No mAP or biological claims."}
    new_output(out)
    return finish(out, report)


def scores_summary(path: Path, out: Path, method_col: str, query_col: str, eval_col: str,
                   metric: str, condition: str, delimiter: str) -> dict[str, Any]:
    """Aggregate existing per-query metrics only; no retrieval or bootstrap is reimplemented."""
    if len({method_col, query_col, eval_col, metric}) != 4:
        raise ValueError("Score column roles must be distinct")
    h = digest(path)
    groups: dict[str, dict[str, tuple[bool, float | None]]] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fields = {method_col, query_col, eval_col, metric}
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("Duplicate score column names; supply an unambiguous header")
        if not fields.issubset(headers):
            raise ValueError("Missing explicit score columns; set column options to the real schema")
        for i, row in enumerate(reader, 1):
            if i > 1_000_000:
                raise ValueError("Input exceeds the bounded score-summary limit")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Score row at line {reader.line_num} has a different number of fields from its header")
            method, q = row[method_col], row[query_col]
            validate_ids([method]); validate_ids([q])
            target = groups.setdefault(method, {})
            if q in target:
                raise ValueError("Duplicate method/query entry; select one condition before analysis")
            value = row[eval_col].strip().lower()
            if value not in {"true", "false", "1", "0"}:
                raise ValueError("Evaluable must be explicit true/false or 1/0; no bool(string) coercion")
            evaluable = value in {"true", "1"}
            raw = row[metric].strip()
            score = None
            if evaluable:
                score = float(raw)
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError("Evaluable metrics must be finite values in [0,1]")
            elif raw.lower() not in {"", "nan", "na", "null", "none"}:
                raise ValueError("Nonevaluable scores must be missing, not zero or another numeric value")
            target[q] = (evaluable, score)
    if not groups:
        raise ValueError("No score rows")
    first = next(iter(groups.values()))
    for rows in groups.values():
        if set(rows) != set(first) or any(rows[q][0] != first[q][0] for q in first):
            raise ValueError("Methods differ in query population/evaluability; no silent intersection or score delta")
    means = {}
    for name, rows in groups.items():
        values = [s for e, s in rows.values() if e]
        means[name] = None if not values else math.fsum(values) / len(values)
    eval_n = sum(e for e, _ in first.values())
    pairs = [{"left": a, "right": b,
              "mean_paired_difference_left_minus_right": None if eval_n == 0 else means[a] - means[b]}
             for a, b in itertools.combinations(groups, 2)]
    if digest(path) != h:
        raise ValueError("Scores changed while reading")
    report = {"scope": "summary_of_preexisting_scores_not_new_retrieval_or_bootstrap", "input_sha256": h,
              "condition_label": condition, "contract_compatibility": "operator_declared_not_independently_verified",
              "metric": metric, "total_queries_per_method": len(first), "evaluable_queries_per_method": eval_n,
              "nonevaluable_queries_per_method": len(first) - eval_n, "coverage": eval_n / len(first),
              "conditional_mean_by_method": means, "paired_mean_differences": pairs,
              "confidence_intervals": "not_computed_use_existing_reviewed_repository_bootstrap",
              "warning": "Select exactly one frozen contract, split, query condition, and candidate population before summarizing."}
    new_output(out)
    return finish(out, report)


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sp = parser.add_subparsers(dest="command", required=True)
    p = sp.add_parser("prepare-images", help="Validate selected inputs and build native-format image inventory; no transforms")
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--settings", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sp.add_parser("npz-info", help="Print array keys/shapes/dtypes, never array values or record IDs")
    p.add_argument("npz", type=Path)
    p = sp.add_parser("analyze", help="Label-free geometry and self-excluded neighbors from existing vectors")
    p.add_argument("--npz", type=Path, required=True)
    p.add_argument("--vectors-key", default="auto")
    p.add_argument("--ids-key", default="auto")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--expected-dim", type=int)
    p.add_argument("--require-unit", action="store_true")
    p.add_argument("--require-float32", action="store_true")
    p = sp.add_parser("compare", help="Compare within-representation geometry, not cross-model raw vectors")
    p.add_argument("--representation", nargs=4, action="append", required=True, metavar=("NAME", "NPZ", "VECTORS_KEY", "IDS_KEY"))
    p.add_argument("--unit", choices=("image", "well", "treatment", "record"), required=True)
    p.add_argument("--condition-label", required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--out", type=Path, required=True)
    p = sp.add_parser("scores-summary", help="Summarize existing keyed per-query scores; no new benchmark or bootstrap")
    p.add_argument("--scores", type=Path, required=True)
    p.add_argument("--method-column", default="method")
    p.add_argument("--query-column", default="query_id")
    p.add_argument("--evaluable-column", default="evaluable")
    p.add_argument("--metric", default="average_precision")
    p.add_argument("--delimiter", choices=("tsv", "csv"), default="tsv")
    p.add_argument("--condition-label", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    try:
        if a.command == "prepare-images":
            report = prepare_images(a.selection, a.data_root, a.settings, a.out)
        elif a.command == "npz-info":
            report = {"arrays": npz_headers(a.npz), "values_printed": False}
        elif a.command == "analyze":
            report = analyze(a.npz, a.vectors_key, a.ids_key, a.out, a.k, a.expected_dim, a.require_unit, a.require_float32)
        elif a.command == "compare":
            report = compare(a.representation, a.unit, a.condition_label, a.out, a.k)
        else:
            report = scores_summary(a.scores, a.out, a.method_column, a.query_column, a.evaluable_column,
                                    a.metric, a.condition_label, "\t" if a.delimiter == "tsv" else ",")
        print(json.dumps(report, indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"STOP: {type(exc).__name__}: {exc}") from exc


if __name__ == "__main__":
    main()
