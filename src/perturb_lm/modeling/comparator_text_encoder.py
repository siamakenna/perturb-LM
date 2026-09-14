"""Frozen text encoders used as Phase 3C comparators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ComparatorTextEncoderSpec:
    """Public-safe immutable configuration for a comparator encoder."""

    repo_id: str
    revision: str
    embedding_dimension: int
    max_length: int
    pooling: str
    normalization: str


MEDCPT_SPEC = ComparatorTextEncoderSpec(
    repo_id="ncbi/MedCPT-Query-Encoder",
    revision="d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc",
    embedding_dimension=768,
    max_length=64,
    pooling="cls_last_hidden_state",
    normalization="none",
)

BIOLORD_SPEC = ComparatorTextEncoderSpec(
    repo_id="FremyCompany/BioLORD-2023",
    revision="167aab527b238a50ca65224e6319215d2ff4fc9f",
    embedding_dimension=768,
    max_length=128,
    pooling="attention_mask_mean",
    normalization="l2",
)


def _resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested

    if torch.cuda.is_available():
        return "cuda"

    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"

    return "cpu"


def _mean_pool_last_hidden_state(last_hidden_state, attention_mask):
    import torch

    expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size())
    expanded = expanded.to(last_hidden_state.dtype)

    numerator = torch.sum(last_hidden_state * expanded, dim=1)
    denominator = torch.clamp(expanded.sum(dim=1), min=1e-9)

    return numerator / denominator


class _FrozenComparatorTextEncoder:
    spec: ComparatorTextEncoderSpec

    def __init__(
        self,
        model_path: str | Path,
        *,
        batch_size: int = 16,
        device: str = "auto",
    ) -> None:
        self.model_path = Path(model_path).expanduser()
        self.batch_size = int(batch_size)
        self.device_request = str(device)

        if self.batch_size < 1:
            raise ValueError("batch_size must be positive.")

        if not self.model_path.is_dir():
            raise FileNotFoundError(
                f"Frozen comparator snapshot does not exist: {self.model_path}"
            )

        self._tokenizer = None
        self._model = None
        self._device = None

    @property
    def embedding_dimension(self) -> int:
        return self.spec.embedding_dimension

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _ensure_loaded(self) -> None:
        if self.is_loaded:
            return

        from transformers import AutoModel, AutoTokenizer

        self._device = _resolve_device(self.device_request)

        self._tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )

        self._model = AutoModel.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )

        self._model.eval()
        self._model.to(self._device)

        hidden_size = int(self._model.config.hidden_size)

        if hidden_size != self.embedding_dimension:
            raise ValueError(
                "Comparator hidden dimension does not match frozen contract: "
                f"{hidden_size} != {self.embedding_dimension}"
            )

    def _pool(self, last_hidden_state, attention_mask):
        raise NotImplementedError

    def encode(self, texts: list[str]) -> np.ndarray:
        import torch

        self._ensure_loaded()

        if not texts:
            return np.empty(
                (0, self.embedding_dimension),
                dtype=np.float32,
            )

        chunks: list[np.ndarray] = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]

            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.spec.max_length,
                return_tensors="pt",
            )

            encoded = {
                key: value.to(self._device)
                for key, value in encoded.items()
            }

            with torch.inference_mode():
                output = self._model(**encoded)
                pooled = self._pool(
                    output.last_hidden_state,
                    encoded["attention_mask"],
                )

            chunks.append(
                pooled.detach().float().cpu().numpy()
            )

        result = np.concatenate(chunks, axis=0).astype(
            np.float32,
            copy=False,
        )

        if result.shape != (
            len(texts),
            self.embedding_dimension,
        ):
            raise ValueError(
                "Unexpected comparator embedding shape: "
                f"{result.shape}"
            )

        if not np.isfinite(result).all():
            raise ValueError(
                "Comparator encoder generated NaN or infinite values."
            )

        return result


class MedCPTTextEncoder(_FrozenComparatorTextEncoder):
    """Frozen MedCPT query encoder."""

    spec = MEDCPT_SPEC

    def _pool(self, last_hidden_state, attention_mask):
        del attention_mask
        return last_hidden_state[:, 0, :]


class BioLORDTextEncoder(_FrozenComparatorTextEncoder):
    """Frozen BioLORD-2023 sentence encoder."""

    spec = BIOLORD_SPEC

    def _pool(self, last_hidden_state, attention_mask):
        import torch.nn.functional as F

        pooled = _mean_pool_last_hidden_state(
            last_hidden_state,
            attention_mask,
        )

        return F.normalize(
            pooled,
            p=2,
            dim=1,
        )
