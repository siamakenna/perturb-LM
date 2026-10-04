"""Pinned offline assets, lazy inference, and atomic content-addressed representation caches."""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import yaml
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from perturb_lm.sklearn_api.datasets import file_checksum


@dataclass(frozen=True)
class AssetSpec:
    name: str
    identifier: str
    revision: str | None
    backend: str
    dimension: int
    input_kind: str
    pooling: str = "mean"
    normalize: bool = True
    max_length: int = 512
    input_shape: tuple[int, ...] = ()
    required_packages: tuple[str, ...] = ("torch", "transformers")
    code_revision: str | None = None
    code_approval_required: bool = False
    blockers: tuple[str, ...] = ()

    def validate(self):
        if not self.revision or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise ValueError(f"needs_model_prefetch: unresolved immutable revision for {self.name}")
        if self.dimension < 1 or self.input_kind not in {"text", "image", "channel_features"}:
            raise ValueError("Invalid model input/dimension specification")
        if self.blockers:
            raise ValueError("; ".join(self.blockers))


def asset_catalog() -> dict[str, AssetSpec]:
    path = Path(__file__).resolve().parents[3] / "configs/benchmark_v2/model_assets.yaml"
    payload = yaml.safe_load(path.read_text())
    result = {}
    for name, values in payload["models"].items():
        values = dict(values)
        for key in ("input_shape", "required_packages", "blockers"):
            if key in values:
                values[key] = tuple(values[key])
        result[name] = AssetSpec(name=name, **values)
    return result


def digest(value) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def validate_asset(path: Path, spec: AssetSpec, approve_model_code: bool = False) -> dict:
    spec.validate()
    if spec.code_approval_required and not approve_model_code:
        raise ValueError("needs_scientific_approval: review pinned local model code and opt in")
    manifest_path = path / "asset.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"needs_model_prefetch: stage {spec.name} at {path} with asset.json"
        )
    payload = json.loads(manifest_path.read_text())
    if payload.get("identifier") != spec.identifier or payload.get("revision") != spec.revision:
        raise ValueError("Model asset identity/revision mismatch")
    checksums = payload.get("checksums", {})
    if not checksums or not payload.get("complete"):
        raise ValueError("Incomplete model asset manifest")
    for name, checksum in checksums.items():
        file = (path / name).resolve()
        if (
            not file.is_relative_to(path.resolve())
            or not file.is_file()
            or file_checksum(file) != checksum
        ):
            raise ValueError("Model asset checksum mismatch or incomplete asset")
    return payload


def optional_import(name):
    try:
        return importlib.import_module(name)
    except ImportError as error:
        raise ImportError(
            f"Optional backend requires {name}; install the benchmark-models extra "
            "and model-specific dependencies in PLM_ENV"
        ) from error


def load_backend(spec: AssetSpec, local_path: Path, device: str, approve_model_code: bool):
    """Only this boundary is mocked in local model tests; no online model-name loading."""
    torch = optional_import("torch")
    for package in spec.required_packages:
        optional_import(package)
    if spec.backend in {"hf_text", "hf_image", "openphenom"}:
        transformers = optional_import("transformers")
        model = transformers.AutoModel.from_pretrained(
            str(local_path),
            local_files_only=True,
            trust_remote_code=approve_model_code if spec.backend == "openphenom" else False,
        )
        tokenizer = (
            transformers.AutoTokenizer.from_pretrained(str(local_path), local_files_only=True)
            if spec.input_kind == "text"
            else None
        )
        processor = (
            transformers.AutoImageProcessor.from_pretrained(str(local_path), local_files_only=True)
            if spec.backend == "hf_image"
            else None
        )
    elif spec.backend == "open_clip_text":
        open_clip = optional_import("open_clip")
        transformers = optional_import("transformers")
        config = json.loads((local_path / "open_clip_config.json").read_text())["model_cfg"]
        config["text_cfg"]["hf_model_name"] = str(local_path / "text_config")
        config["text_cfg"]["hf_tokenizer_name"] = str(local_path)
        config["text_cfg"]["hf_model_pretrained"] = False
        config_dir = local_path / "runtime_config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "plm_biomedclip.json").write_text(json.dumps(config))
        open_clip.add_model_config(config_dir)
        model, _, _ = open_clip.create_model_and_transforms(
            "plm_biomedclip", pretrained=str(local_path / "open_clip_pytorch_model.bin")
        )
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(local_path), local_files_only=True
        )
        processor = None
    elif spec.backend == "cellclip":
        # The separately pinned CellCLIP source supplies the architecture, not weights.
        module = optional_import("model")
        if not hasattr(module, "MILCLIP"):
            raise ImportError(
                "Install the pinned CellCLIP source on PYTHONPATH; expected model.MILCLIP"
            )
        config = json.loads((local_path / "config.json").read_text())
        model = module.MILCLIP(**config)
        safetensors = optional_import("safetensors.torch")
        model.load_state_dict(
            safetensors.load_file(str(local_path / "model.safetensors")), strict=True
        )
        tokenizer = processor = None
    else:
        raise ValueError(f"Unsupported model backend: {spec.backend}")
    model = model.to(device).eval()

    def encode(batch):
        with torch.inference_mode():
            if spec.input_kind == "text":
                encoded = tokenizer(
                    list(batch),
                    padding=True,
                    truncation=True,
                    max_length=spec.max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(device) for key, value in encoded.items()}
                if spec.backend == "open_clip_text":
                    ids = encoded["input_ids"]
                    if ids.shape[1] < spec.max_length:
                        ids = torch.nn.functional.pad(
                            ids, (0, spec.max_length - ids.shape[1]), value=tokenizer.pad_token_id
                        )
                    vector = model.encode_text(ids)
                else:
                    hidden = model(**encoded).last_hidden_state
                    if spec.pooling == "cls":
                        vector = hidden[:, 0]
                    else:
                        mask = encoded["attention_mask"].unsqueeze(-1)
                        vector = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            elif spec.backend == "openphenom":
                model.return_channelwise_embeddings = False
                vector = model.predict(torch.as_tensor(np.asarray(batch), device=device))
            elif spec.backend == "cellclip":
                vector = model.encode_image(
                    torch.as_tensor(np.asarray(batch), dtype=torch.float32, device=device)
                )
            else:
                inputs = processor(images=list(batch), return_tensors="pt")
                vector = model(
                    **{key: value.to(device) for key, value in inputs.items()}
                ).last_hidden_state[:, 0]
            return vector.detach().float().cpu().numpy()

    return encode


class LocalModelEmbedder(TransformerMixin, BaseEstimator):
    def __init__(
        self,
        spec: AssetSpec,
        asset_root,
        cache_root=None,
        batch_size=16,
        device="cpu",
        approve_model_code=False,
    ):
        self.spec = spec
        self.asset_root = asset_root
        self.cache_root = cache_root
        self.batch_size = batch_size
        self.device = device
        self.approve_model_code = approve_model_code

    def fit(self, X, y=None):
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self.asset_manifest_ = validate_asset(
            Path(self.asset_root), self.spec, self.approve_model_code
        )
        self._validate_inputs(X)
        return self

    def _validate_inputs(self, X):
        if self.spec.input_kind == "text":
            if not all(isinstance(value, str) for value in X):
                raise ValueError("Text models require strings")
        else:
            matrix = np.asarray(X)
            if (
                matrix.ndim != len(self.spec.input_shape) + 1
                or any(
                    expected > 0 and actual != expected
                    for actual, expected in zip(
                        matrix.shape[1:], self.spec.input_shape, strict=True
                    )
                )
                or not np.isfinite(matrix).all()
            ):
                raise ValueError("Model input schema/dimension mismatch")

    def transform(self, X):
        check_is_fitted(self, "asset_manifest_")
        self._validate_inputs(X)
        import hashlib

        inputs_hash = (
            digest(list(X))
            if self.spec.input_kind == "text"
            else hashlib.sha256(np.asarray(X).tobytes()).hexdigest()
        )
        key = digest(
            {
                "model": asdict(self.spec),
                "inputs": inputs_hash,
                "assets": self.asset_manifest_,
                "device": self.device,
            }
        )
        cache = Path(self.cache_root) / key if self.cache_root is not None else None
        if cache is not None and (cache / "complete.json").exists():
            saved = json.loads((cache / "complete.json").read_text())
            path = cache / "embeddings.npy"
            if (
                saved.get("key") != key
                or not path.exists()
                or file_checksum(path) != saved.get("checksum")
            ):
                raise ValueError("Corrupt representation cache; quarantine before retry")
            result = np.load(path, allow_pickle=False)
            self._validate_output(result, len(X))
            return result
        if cache is not None and cache.exists():
            raise ValueError("Incomplete representation cache; quarantine before retry")
        if not hasattr(self, "backend_"):
            self.backend_ = load_backend(
                self.spec, Path(self.asset_root), self.device, self.approve_model_code
            )
        chunks = [
            np.asarray(self.backend_(X[start : start + self.batch_size]), dtype=np.float32)
            for start in range(0, len(X), self.batch_size)
        ]
        result = (
            np.concatenate(chunks)
            if chunks
            else np.empty((0, self.spec.dimension), dtype=np.float32)
        )
        self._validate_output(result, len(X))
        if self.spec.normalize:
            result = result / np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_name(cache.name + f".working-{os.getpid()}")
            temporary.mkdir(exist_ok=False)
            try:
                np.save(temporary / "embeddings.npy", result, allow_pickle=False)
                (temporary / "complete.json").write_text(
                    json.dumps(
                        {"key": key, "checksum": file_checksum(temporary / "embeddings.npy")}
                    )
                )
                if cache.exists():
                    shutil.rmtree(temporary)
                else:
                    temporary.rename(cache)
            except BaseException:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        return result

    def _validate_output(self, result, count):
        if result.shape != (count, self.spec.dimension) or not np.isfinite(result).all():
            raise ValueError(
                "Backend representation shape/nonfinite output violates model contract"
            )
