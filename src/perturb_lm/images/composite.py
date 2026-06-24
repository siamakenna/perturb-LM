"""Render microscopy channel images into model-ready RGB composites."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


CHANNEL_COLUMNS = [f"image_path_ch{channel}" for channel in range(1, 7)]

DEFAULT_RGB_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "image_path_ch1": (0.0, 0.0, 1.0),
    "image_path_ch2": (0.0, 1.0, 0.0),
    "image_path_ch3": (1.0, 0.0, 0.0),
    "image_path_ch4": (1.0, 0.0, 1.0),
    "image_path_ch5": (0.0, 1.0, 1.0),
    "image_path_ch6": (1.0, 1.0, 0.0),
}


def validate_channel_paths(paths: list[Path]) -> list[Path]:
    """Validate that requested channel paths exist before composite rendering."""

    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing channel image(s): {', '.join(str(path) for path in missing)}")
    return paths


def resolve_image_path(path: object, raw_root: Path | None = None) -> Path:
    """Resolve an image path from a manifest cell, optionally relative to a raw root."""

    image_path = Path(str(path))
    if image_path.is_absolute() or raw_root is None:
        return image_path
    return raw_root / image_path


def available_channel_paths(
    row: pd.Series,
    *,
    raw_root: Path | None = None,
    channel_columns: list[str] | None = None,
) -> dict[str, Path]:
    """Return channel paths from a manifest row that are nonempty and exist."""

    paths: dict[str, Path] = {}
    for column in channel_columns or CHANNEL_COLUMNS:
        value = row.get(column, "")
        if pd.isna(value) or str(value).strip() == "":
            continue
        path = resolve_image_path(value, raw_root)
        if path.exists():
            paths[column] = path
    return paths


def render_rgb_composite(
    channel_paths: dict[str, Path],
    *,
    weights: dict[str, tuple[float, float, float]] | None = None,
    output_size: tuple[int, int] | None = None,
) -> Image.Image:
    """Render a false-color RGB composite from grayscale channel image paths."""

    if not channel_paths:
        raise ValueError("At least one existing channel image is required to render a composite.")
    weights = weights or DEFAULT_RGB_WEIGHTS
    rgb: np.ndarray | None = None
    for column, path in channel_paths.items():
        channel = load_grayscale_image(path)
        if rgb is None:
            rgb = np.zeros((*channel.shape, 3), dtype=np.float32)
        elif channel.shape != rgb.shape[:2]:
            channel = np.asarray(
                Image.fromarray(channel).resize((rgb.shape[1], rgb.shape[0]), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
        scaled = robust_uint8(channel).astype(np.float32) / 255.0
        red, green, blue = weights.get(column, (1.0, 1.0, 1.0))
        rgb[..., 0] += scaled * red
        rgb[..., 1] += scaled * green
        rgb[..., 2] += scaled * blue
    assert rgb is not None
    rgb = np.clip(rgb, 0.0, 1.0)
    image = Image.fromarray((rgb * 255).astype(np.uint8), mode="RGB")
    if output_size is not None:
        image = image.resize(output_size, Image.Resampling.BILINEAR)
    return image


def render_site_composite(
    row: pd.Series,
    out_path: Path,
    *,
    raw_root: Path | None = None,
    output_size: tuple[int, int] | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    """Render one manifest row to a PNG composite and return an output manifest row."""

    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        return _composite_row(row, out_path, "exists", n_channels=None)
    channel_paths = available_channel_paths(row, raw_root=raw_root)
    if not channel_paths:
        return _composite_row(row, out_path, "missing_channels", n_channels=0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = render_rgb_composite(channel_paths, output_size=output_size)
    image.save(out_path)
    return _composite_row(row, out_path, "rendered", n_channels=len(channel_paths))


def render_manifest_composites(
    site_manifest: pd.DataFrame,
    out_dir: Path,
    *,
    raw_root: Path | None = None,
    limit: int | None = None,
    output_size: tuple[int, int] | None = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Render composites for manifest rows and return a composite manifest."""

    rows = []
    frame = site_manifest.head(limit).copy() if limit else site_manifest.copy()
    for _, row in frame.iterrows():
        site_id = _safe_filename(row.get("site_id", f"site_{len(rows)}"))
        out_path = Path(out_dir) / f"{site_id}.png"
        rows.append(
            render_site_composite(
                row,
                out_path,
                raw_root=raw_root,
                output_size=output_size,
                overwrite=overwrite,
            )
        )
    return pd.DataFrame(rows)


def load_grayscale_image(path: Path) -> np.ndarray:
    """Load an image as a 2D floating-point grayscale array."""

    with Image.open(path) as image:
        array = np.asarray(image)
    if array.ndim == 3:
        array = array[..., :3].mean(axis=2)
    if array.ndim != 2:
        raise ValueError(f"Expected a 2D grayscale-compatible image at {path}, got shape {array.shape}.")
    return array.astype(np.float32)


def robust_uint8(channel: np.ndarray, lower: float = 1.0, upper: float = 99.8) -> np.ndarray:
    """Scale a numeric channel to uint8 with percentile clipping."""

    values = np.asarray(channel, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(values.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [lower, upper])
    if hi <= lo:
        hi = float(finite.max())
        lo = float(finite.min())
    if hi <= lo:
        return np.zeros(values.shape, dtype=np.uint8)
    scaled = (np.clip(values, lo, hi) - lo) / (hi - lo)
    return (scaled * 255).astype(np.uint8)


def _composite_row(
    row: pd.Series,
    out_path: Path,
    status: str,
    *,
    n_channels: int | None,
) -> dict[str, object]:
    return {
        "dataset": row.get("dataset", ""),
        "site_id": row.get("site_id", ""),
        "experiment": row.get("experiment", ""),
        "plate": row.get("plate", ""),
        "well": row.get("well", ""),
        "site": row.get("site", ""),
        "perturbation_id": row.get("perturbation_id", ""),
        "perturbation_name": row.get("perturbation_name", ""),
        "composite_path": str(out_path),
        "composite_status": status,
        "n_channels_rendered": n_channels,
    }


def _safe_filename(value: object) -> str:
    text = str(value).strip() or "site"
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in text)
