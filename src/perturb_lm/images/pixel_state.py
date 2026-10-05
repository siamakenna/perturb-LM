"""Versioned JSON persistence for the existing pixel transformer and image index."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

from perturb_lm.images import pixel_analyzer
from perturb_lm.images.pixel_analyzer import FEATURE_SCHEMA, PixelMorphologyTransformer


def checksum(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def write_record(path, payload):
    """Write in an unpublished working directory; the workflow publishes atomically."""
    envelope = {"payload": payload, "sha256": checksum(payload)}
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(envelope, handle, indent=2, allow_nan=False)


def read_record(path):
    try:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = envelope["payload"]
        if checksum(payload) != envelope["sha256"]:
            raise ValueError("checksum mismatch")
        return payload
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid or corrupted pixel artifact: {error}") from error


def runtime_versions():
    return {
        name: importlib.metadata.version(name)
        for name in ("numpy", "scipy", "scikit-image", "scikit-learn", "tifffile")
    }


def extractor_checksum():
    return hashlib.sha256(Path(pixel_analyzer.__file__).read_bytes()).hexdigest()


def channel_schema(channels):
    if (
        not isinstance(channels, (tuple, list))
        or not channels
        or any(not isinstance(c, str) or not c.strip() for c in channels)
        or len(set(channels)) != len(channels)
    ):
        raise ValueError("Provide unique, nonempty channel names in stored channel order.")
    return list(channels)


def state_payload(model, channels):
    check_is_fitted(model, "feature_names_out_")
    channels = channel_schema(channels)
    if len(channels) != model.n_channels_in_:
        raise ValueError("Channel schema differs from fitted preprocessing.")
    if model.get_params() != model.fitted_params_:
        raise ValueError("Parameters changed after fit.")
    scaler = model.scaler_
    return {
        "format": "pixel-preprocessing-v1",
        "feature_schema": FEATURE_SCHEMA,
        "features": model.get_feature_names_out().tolist(),
        "units": model.feature_units(model.n_channels_in_),
        "channels": channels,
        "parameters": {
            key: value.item() if isinstance(value, np.generic) else value
            for key, value in model.get_params().items()
        },
        "versions": runtime_versions(),
        "extractor_sha256": extractor_checksum(),
        "scaler": None
        if scaler is None
        else {
            "mean": scaler.mean_.tolist(),
            "var": scaler.var_.tolist(),
            "scale": scaler.scale_.tolist(),
            "n_samples": int(scaler.n_samples_seen_),
        },
    }


def restore_model(payload):
    """Validate before constructing any fitted state. Never unpickle user files."""
    try:
        if (
            payload["format"] != "pixel-preprocessing-v1"
            or payload["feature_schema"] != FEATURE_SCHEMA
        ):
            raise ValueError("Unknown preprocessing or feature schema.")
        channels = channel_schema(payload["channels"])
        if payload["versions"] != runtime_versions():
            raise ValueError(
                "Preprocessing dependency versions differ; use the recorded environment."
            )
        if payload["extractor_sha256"] != extractor_checksum():
            raise ValueError("Feature extractor changed; use the recorded implementation.")
        parameters = payload["parameters"]
        if set(parameters) != set(PixelMorphologyTransformer().get_params()):
            raise ValueError("Unknown preprocessing parameters.")
        model = PixelMorphologyTransformer(**parameters)
        model._validate_parameters()
        names = model._names(len(channels))
        if payload["features"] != names.tolist() or payload["units"] != model.feature_units(
            len(channels)
        ):
            raise ValueError("Unknown feature schema or units.")
        if model.segmentation_channel >= len(channels):
            raise ValueError("Incompatible segmentation channel.")
        saved = payload["scaler"]
        if not model.scale_features:
            if saved is not None:
                raise ValueError("Unexpected scaler for unscaled preprocessing.")
            scaler = None
        else:
            if type(saved["n_samples"]) is not int or saved["n_samples"] < 1:
                raise ValueError("Invalid reference sample count.")
            arrays = [np.asarray(saved[key], dtype=float) for key in ("mean", "var", "scale")]
            if any(a.shape != (len(names),) or not np.isfinite(a).all() for a in arrays):
                raise ValueError("Invalid scaler dimensions or nonfinite state.")
            mean, var, scale = arrays
            if np.any(var < 0) or np.any(scale <= 0):
                raise ValueError("Invalid scaler variance or scale.")
            scaler = StandardScaler()
            scaler.mean_, scaler.var_, scaler.scale_ = mean, var, scale
            scaler.n_features_in_ = len(names)
            scaler.n_samples_seen_ = saved["n_samples"]
        model.n_channels_in_ = len(channels)
        model.feature_names_out_ = names
        model.scaler_ = scaler
        model.fitted_params_ = parameters.copy()
        return model
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid preprocessing state structure.") from error


def load_preprocessor(path, *, channels):
    payload = read_record(path)
    model = restore_model(payload)
    if payload["channels"] != channel_schema(channels):
        raise ValueError("Incompatible channels: names/order differ from reference state.")
    return model, payload


def load_index(directory, *, channels):
    directory = Path(directory)
    model, state = load_preprocessor(directory / "state.json", channels=channels)
    index = read_record(directory / "index.json")
    try:
        if index["format"] != "pixel-index-v1" or index["state_sha256"] != checksum(state):
            raise ValueError("Index does not match preprocessing state.")
        if index["features"] != state["features"]:
            raise ValueError("Unknown index feature schema.")
        rows = index["rows"]
        ids = [row["image_id"] for row in rows]
        if (
            not ids
            or any(not isinstance(i, str) or not i.strip() for i in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Index row identities must be unique and nonempty.")
        raw, scaled = np.asarray(index["raw"], float), np.asarray(index["scaled"], float)
        if any(
            a.shape != (len(rows), len(state["features"])) or not np.isfinite(a).all()
            for a in (raw, scaled)
        ):
            raise ValueError("Invalid index matrices or row alignment.")
        expected = raw if model.scaler_ is None else model.scaler_.transform(raw)
        if not np.allclose(expected, scaled, rtol=1e-12, atol=1e-12):
            raise ValueError("Index scaling differs from fitted state.")
        return model, state, index
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid pixel index structure.") from error
