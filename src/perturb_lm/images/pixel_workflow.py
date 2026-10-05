"""Local TIFF analysis, reference fitting and search using PixelMorphologyTransformer."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import pairwise_distances

from perturb_lm.images.pixel_analyzer import (
    PixelInputError,
    PixelMorphologyTransformer,
    read_tiff_chw,
)
from perturb_lm.images.pixel_demo import object_preview
from perturb_lm.images.pixel_state import (
    channel_schema,
    checksum,
    load_index,
    load_preprocessor,
    state_payload,
    write_record,
)

OBJECT_COLUMNS = [
    "image_id",
    "object_id",
    "area_px2",
    "perimeter_px",
    "centroid_y_px",
    "centroid_x_px",
    "eccentricity",
    "solidity",
]
NEIGHBOR_COLUMNS = ["query_id", "rank", "reference_id", "distance"]


def _csv(path, columns, rows):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _thumbnail(picture):
    picture = picture.copy()
    picture.thumbnail((192, 192))
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _table(rows, columns):
    def display(value):
        return html.escape(format(value, ".6g") if isinstance(value, float) else str(value))

    heading = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{display(row.get(c, ''))}</td>" for c in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table>"


def _report(out, manifest, qc, rows, objects, neighbors, references):
    sections = [
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>Pixel analysis</title>",
        "<style>body{font:16px system-ui;margin:2rem;max-width:1200px;overflow-wrap:anywhere}"
        "table{border-collapse:collapse;"
        "display:block;overflow:auto}td,th{padding:.4rem;border:1px solid #bbb;white-space:nowrap}"
        "img{max-width:192px}"
        "section{margin:2rem 0}figure{display:inline-block;margin:.5rem}</style>",
        "<h1>Local pixel-only image analysis</h1>",
        "<p>Exploratory watershed objects and image similarity; "
        "no inferred treatment or cell identity. Intensities retain source units; "
        "lengths/areas are pixels/pixel². Preview contrast is display-only.</p>",
        f"<p>{manifest['n_accepted']} accepted · {manifest['n_excluded']} excluded · "
        f"{html.escape(manifest['mode'])} mode. "
        "<a href='run.json'>Run configuration</a></p>",
        "<h2>Quality control — excluded observations are not indexed</h2>",
        _table(qc, ["image_id", "path", "status", "reason", "detail"]),
        "<p><a href='raw_features.csv'>Raw features</a> · "
        "<a href='measurements.csv'>Object measurements</a>"
        " · <a href='units.json'>Units and channel schema</a> · <a href='qc.csv'>QC CSV</a></p>",
    ]
    if (out / "scaled_features.csv").exists():
        sections.append("<p><a href='scaled_features.csv'>Reference-scaled features</a></p>")
    by_reference = {row["image_id"]: row for row in references}
    for row in rows:
        identity = row["image_id"]
        sections.extend(
            [
                "<section><h2>" + html.escape(identity) + "</h2>",
                "<p>" + html.escape(row["path"]) + "</p>",
            ]
        )
        for c, name in enumerate(manifest["channels"]):
            sections.append(
                f"<figure><img src='previews/{row['input_row']:06d}-c{c}.png' "
                f"alt='Channel {c}'><figcaption>{html.escape(name)}</figcaption></figure>"
            )
        sections.append(
            f"<figure><img src='previews/{row['input_row']:06d}-overlay.png' "
            "alt='Object boundaries'><figcaption>Object boundaries</figcaption></figure>"
        )
        sections.append(
            f"<figure><img src='previews/{row['input_row']:06d}-mask.png' "
            "alt='Object labels'><figcaption>Object labels (display colors)</figcaption></figure>"
        )
        sections.append(
            f"<p><a href='masks/{row['input_row']:06d}.tif'>Integer object mask TIFF</a></p>"
        )
        measurements = [obj for obj in objects if obj["image_id"] == identity]
        sections.append(
            _table(measurements[:100], list(measurements[0]) if measurements else OBJECT_COLUMNS)
        )
        if len(measurements) > 100:
            sections.append("<p>First 100 objects shown; all measurements are in the CSV.</p>")
        nearest = [neighbor for neighbor in neighbors if neighbor["query_id"] == identity]
        if nearest:
            sections.extend(
                [
                    "<h3>Reference neighbors — Euclidean distance in scaled feature space</h3>",
                    _table(nearest, NEIGHBOR_COLUMNS),
                ]
            )
            for neighbor in nearest:
                ref = by_reference[neighbor["reference_id"]]
                sections.append(
                    "<figure><img alt='Reference object overlay' src='data:image/png;base64,"
                    + html.escape(ref["thumbnail_png"], quote=True)
                    + "'><figcaption>"
                    + html.escape(ref["image_id"])
                    + "</figcaption></figure>"
                )
        sections.append("</section>")
    sections.append("</html>")
    (out / "report.html").write_text("\n".join(sections), encoding="utf-8")


def run_images(
    paths,
    *,
    output,
    axes,
    channels,
    mode="analyze",
    image_ids=None,
    reference=None,
    state=None,
    segmentation_channel=0,
    min_object_area=8,
    smooth_sigma=1.0,
    min_peak_distance=4,
    series=None,
    top_k=5,
):
    """Analyze paths independently of labels, or fit/search a reference-only index.

    Every input gets a row in qc.csv. Invalid images never receive a feature row.
    Row IDs are caller-supplied or ordinal; file paths are provenance only.
    A raw-only analysis never fits a scaler. Use mode=fit on reference images or
    supply state to mode=analyze to export reference-scaled features.
    """
    if mode not in {"analyze", "fit", "search"}:
        raise ValueError("Unknown image workflow mode.")
    if axes not in {"YX", "CYX", "YXC"}:
        raise ValueError("Supply explicit axes YX, CYX, or YXC.")
    channels = channel_schema(channels)
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    paths = list(paths)
    if not paths:
        raise ValueError("Supply at least one TIFF path.")
    ids = (
        list(image_ids) if image_ids is not None else [f"image_{i:06d}" for i in range(len(paths))]
    )
    if (
        len(ids) != len(paths)
        or len(set(ids)) != len(ids)
        or any(not isinstance(i, str) or not i.strip() for i in ids)
    ):
        raise ValueError("Supply one unique, nonempty image ID per input path.")
    if reference is not None and mode != "search" or state is not None and mode != "analyze":
        raise ValueError("Reference is for search; state is for analyze only.")
    if (state is not None or mode == "search") and (
        segmentation_channel,
        min_object_area,
        smooth_sigma,
        min_peak_distance,
    ) != (0, 8, 1.0, 4):
        raise ValueError("Saved state supplies segmentation parameters; overrides are not allowed.")
    saved, index = None, None
    if mode == "search":
        if reference is None:
            raise ValueError("Search requires a reference index.")
        model, saved, index = load_index(reference, channels=channels)
    elif state is not None:
        model, saved = load_preprocessor(state, channels=channels)
    else:
        model = PixelMorphologyTransformer(
            segmentation_channel=segmentation_channel,
            min_object_area=min_object_area,
            smooth_sigma=smooth_sigma,
            min_peak_distance=min_peak_distance,
        )
        model._validate_parameters()
    if model.segmentation_channel >= len(channels):
        raise ValueError("Segmentation channel is outside configured channel order.")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a new directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        result = _execute(
            paths, ids, working, axes, channels, mode, model, saved, index, series, top_k
        )
        if output.exists():
            raise FileExistsError("Output was created by another process.")
        working.rename(output)
    except BaseException:
        shutil.rmtree(working, ignore_errors=True)
        raise
    return result


def _execute(paths, ids, out, axes, channels, mode, model, saved, index, series, top_k):
    from tifffile import imwrite

    (out / "masks").mkdir()
    (out / "previews").mkdir()
    qc, rows, images, raw, objects = [], [], [], [], []
    names = model._names(len(channels)).tolist()
    for ordinal, (path, identity) in enumerate(zip(paths, ids, strict=True)):
        source = str(Path(path).resolve())
        status = {
            "image_id": identity,
            "path": source,
            "input_row": ordinal,
            "status": "excluded",
            "reason": "",
            "detail": "",
        }
        try:
            image = read_tiff_chw(path, axes=axes, series=series)
        except PixelInputError as error:
            status.update(reason=error.code, detail=str(error))
        except (OSError, ValueError, RuntimeError, IndexError) as error:
            status.update(reason="unreadable", detail=f"{type(error).__name__}: {error}")
        else:
            try:
                if image.shape[0] != len(channels):
                    raise PixelInputError(
                        "incompatible_channels",
                        "Decoded channel count differs from explicit schema.",
                    )
                features, mask, measurements = model.measure(image)
                if not mask.any():
                    raise PixelInputError(
                        "no_objects", "No foreground objects survived segmentation; excluded."
                    )
            except (ValueError, FloatingPointError, OverflowError) as error:
                status.update(
                    reason=getattr(error, "code", "invalid_measurements"), detail=str(error)
                )
            else:
                status.update(status="accepted")
                raw.append(features)
                images.append(image)
                objects.extend({"image_id": identity, **obj} for obj in measurements)
                imwrite(
                    out / "masks" / f"{ordinal:06d}.tif",
                    mask.astype(np.int32),
                    photometric="minisblack",
                    metadata={"axes": "YX"},
                )
                picture = object_preview(image, mask, channel=model.segmentation_channel)
                picture.save(out / "previews" / f"{ordinal:06d}-overlay.png")
                mask_rgb = np.stack([(mask * m) % 256 for m in (53, 97, 193)], axis=-1)
                Image.fromarray(mask_rgb.astype(np.uint8)).save(
                    out / "previews" / f"{ordinal:06d}-mask.png"
                )
                for c, plane in enumerate(image):
                    lo, hi = float(plane.min()), float(plane.max())
                    view = np.clip((plane.astype(float) - lo) / max(hi - lo, 1e-12), 0, 1)
                    Image.fromarray((view * 255).astype(np.uint8)).save(
                        out / "previews" / f"{ordinal:06d}-c{c}.png"
                    )
                pixels_hash = hashlib.sha256(
                    json.dumps([image.shape, image.dtype.str]).encode()
                    + np.ascontiguousarray(image).tobytes()
                ).hexdigest()
                rows.append(
                    {
                        "image_id": identity,
                        "input_row": ordinal,
                        "path": source,
                        "pixels_sha256": pixels_hash,
                        "shape": list(image.shape),
                        "dtype": str(image.dtype),
                        "thumbnail_png": _thumbnail(picture),
                    }
                )
        qc.append(status)
    raw = np.asarray(raw, dtype=float).reshape(len(rows), len(names))
    scaled = None
    if mode == "fit" and rows:
        model.fit(images)  # Only accepted reference images enter fit.
        saved = state_payload(model, channels)
        write_record(out / "state.json", saved)
    if saved is not None:
        before = checksum(state_payload(model, channels))
        scaled = (
            raw.copy()
            if model.scaler_ is None
            else (model.scaler_.transform(raw) if len(raw) else raw.copy())
        )
        if not np.isfinite(scaled).all():
            raise ValueError(
                "Nonfinite scaled features; reference/query intensity range is incompatible."
            )
        if checksum(state_payload(model, channels)) != before:
            raise RuntimeError("Inference changed fitted preprocessing.")
    if mode == "fit" and rows:
        write_record(
            out / "index.json",
            {
                "format": "pixel-index-v1",
                "state_sha256": checksum(saved),
                "features": names,
                "rows": rows,
                "raw": raw.tolist(),
                "scaled": scaled.tolist(),
            },
        )
    neighbors = []
    if mode == "search" and rows:
        for row, vector in zip(rows, scaled, strict=True):
            distances = pairwise_distances(
                vector[None, :], np.asarray(index["scaled"]), metric="euclidean"
            )[0]
            # Ties preserve reference row order, never filenames or biological labels.
            for rank, candidate in enumerate(np.argsort(distances, kind="stable")[:top_k], 1):
                neighbors.append(
                    {
                        "query_id": row["image_id"],
                        "rank": rank,
                        "reference_id": index["rows"][candidate]["image_id"],
                        "distance": float(distances[candidate]),
                    }
                )
    for filename, values in (("raw_features.csv", raw), ("scaled_features.csv", scaled)):
        if values is not None:
            _csv(
                out / filename,
                ["image_id", *names],
                [
                    {"image_id": row["image_id"], **dict(zip(names, vector, strict=True))}
                    for row, vector in zip(rows, values, strict=True)
                ],
            )
    measurement_columns = OBJECT_COLUMNS + [
        f"channel_{c}_{suffix}_intensity"
        for c in range(len(channels))
        for suffix in ("mean", "sum")
    ]
    _csv(out / "measurements.csv", measurement_columns, objects)
    _csv(out / "qc.csv", ["image_id", "input_row", "path", "status", "reason", "detail"], qc)
    _csv(out / "neighbors.csv", NEIGHBOR_COLUMNS, neighbors)
    units = {
        "channels": channels,
        "features": dict(zip(names, model.feature_units(len(channels)), strict=True)),
        "scaled_features": "dimensionless reference z-score",
        "measurements": {
            name: (
                "pixel^2"
                if name == "area_px2"
                else "pixel"
                if name.endswith("_px")
                else "source_intensity*pixel_count"
                if name.endswith("_sum_intensity")
                else "source_intensity"
                if name.endswith("_intensity")
                else "identifier"
                if name.endswith("_id")
                else "dimensionless"
            )
            for name in measurement_columns
        },
    }
    (out / "units.json").write_text(json.dumps(units, indent=2) + "\n")
    (out / "images.json").write_text(
        json.dumps(
            [{k: v for k, v in row.items() if k != "thumbnail_png"} for row in rows], indent=2
        )
        + "\n"
    )
    manifest = {
        "mode": mode,
        "axes": axes,
        "channels": channels,
        "series": series,
        "segmentation_parameters": model.get_params(),
        "n_inputs": len(paths),
        "n_accepted": len(rows),
        "n_excluded": len(qc) - len(rows),
        "scaled_features": scaled is not None,
        "state_sha256": checksum(saved) if saved is not None else None,
        "status": "complete" if rows else "no_valid_images",
        "scope": "exploratory_pixel_only",
        "biological_metadata_used": False,
    }
    (out / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _report(out, manifest, qc, rows, objects, neighbors, index["rows"] if index else [])
    checksums = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }
    write_record(out / "complete.json", {"status": manifest["status"], "checksums": checksums})
    return manifest
