"""Frozen text encoder interfaces for controlled Phase 3C experiments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


BIOMEDBERT_MODEL_NAME = "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"
BIOMEDBERT_REVISION = "e1354b7a3a09615f6aba48dfad4b7a613eef7062"
BIOMEDBERT_LICENSE = "MIT"
BIOMEDBERT_EMBEDDING_DIMENSION = 768
BIOMEDBERT_MAX_LENGTH = 512


class TextEncoder(Protocol):
    """Minimal text embedding protocol used by Phase 3C."""

    @property
    def embedding_dimension(self) -> int:
        """Return output embedding dimension without requiring per-call inference."""

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode input texts as a finite two-dimensional array."""


@dataclass(frozen=True)
class TextEncoderSpec:
    """Public-safe encoder selection metadata."""

    model_name: str
    official_source: str
    license: str
    revision: str
    embedding_dimension: int
    pooling_method: str
    max_sequence_length: int
    normalization: str
    device_requirements: str
    selected_because: str
    limitations: str


BIOMEDBERT_SPEC = TextEncoderSpec(
    model_name=BIOMEDBERT_MODEL_NAME,
    official_source=(
        "https://huggingface.co/"
        "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"
    ),
    license=BIOMEDBERT_LICENSE,
    revision=BIOMEDBERT_REVISION,
    embedding_dimension=BIOMEDBERT_EMBEDDING_DIMENSION,
    pooling_method="attention-mask mean pooling over last hidden states",
    max_sequence_length=BIOMEDBERT_MAX_LENGTH,
    normalization="L2 normalize pooled embeddings by default",
    device_requirements="CPU supported; Apple MPS or CUDA may be used when available.",
    selected_because=(
        "It is a Microsoft biomedical BERT model pretrained from scratch on PubMed "
        "abstracts and PubMedCentral full text, has an MIT license, can be pinned by "
        "Hugging Face revision, and is manageable as a frozen local feature extractor."
    ),
    limitations=(
        "BiomedBERT is a masked-language model, not a sentence-transformer trained "
        "directly for retrieval. Mean-pooled embeddings are therefore an explicit "
        "feature-extraction baseline that must beat identifier-stripped TF-IDF before "
        "supporting stronger claims."
    ),
)


@dataclass
class DeterministicFakeTextEncoder:
    """Stable fake encoder for tests and smoke workflows."""

    embedding_dimension_value: int = 16
    seed: int = 0
    normalize: bool = True

    @property
    def embedding_dimension(self) -> int:
        return int(self.embedding_dimension_value)

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            digest = hashlib.sha256(f"{self.seed}|{text}".encode("utf-8")).digest()
            row_seed = int.from_bytes(digest[:8], "little", signed=False)
            rng = np.random.default_rng(row_seed)
            rows.append(rng.normal(size=self.embedding_dimension))
        embeddings = np.asarray(rows, dtype=float)
        if self.normalize:
            embeddings = l2_normalize(embeddings)
        return validate_embedding_matrix(embeddings, expected_dim=self.embedding_dimension)


class FrozenBiomedicalTextEncoder:
    """Lazy, inference-only BiomedBERT wrapper.

    Heavy dependencies are imported only when this encoder is instantiated and used.
    The encoder is frozen: it switches the model to eval mode and always runs under
    ``torch.no_grad()``.
    """

    def __init__(
        self,
        *,
        model_name: str = BIOMEDBERT_MODEL_NAME,
        revision: str = BIOMEDBERT_REVISION,
        device: str = "auto",
        batch_size: int = 16,
        max_length: int = BIOMEDBERT_MAX_LENGTH,
        cache_dir: Path | str | None = None,
        normalize: bool = True,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.device_request = device
        self.batch_size = int(batch_size)
        self.max_length = int(max_length)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.normalize = normalize
        self._tokenizer = None
        self._model = None
        self._device = None
        self._embedding_dimension = BIOMEDBERT_EMBEDDING_DIMENSION

    @property
    def embedding_dimension(self) -> int:
        if self._model is not None:
            return int(self._model.config.hidden_size)
        return int(self._embedding_dimension)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def encode(self, texts: list[str]) -> np.ndarray:
        self._ensure_loaded()
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive.")
        import torch

        rows: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [str(text) for text in texts[start : start + self.batch_size]]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with torch.no_grad():
                output = self._model(**encoded)
            pooled = _mean_pool_torch(output.last_hidden_state, encoded["attention_mask"])
            if self.normalize:
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            rows.append(pooled.detach().cpu().numpy())
        matrix = np.vstack(rows) if rows else np.empty((0, self.embedding_dimension), dtype=float)
        return validate_embedding_matrix(matrix, expected_dim=self.embedding_dimension)

    def _ensure_loaded(self) -> None:
        if self.is_loaded:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - exercised by environment-dependent users.
            raise ImportError(
                "Phase 3C real encoder support requires optional dependencies. "
                "Install with: python -m pip install -e '.[phase3c,dev]'."
            ) from exc
        device = self._select_device(torch)
        kwargs = {"revision": self.revision}
        if self.cache_dir is not None:
            kwargs["cache_dir"] = str(self.cache_dir)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, **kwargs)
        self._model = AutoModel.from_pretrained(self.model_name, **kwargs)
        self._model.to(device)
        self._model.eval()
        for parameter in self._model.parameters():
            parameter.requires_grad_(False)
        self._device = device
        self._embedding_dimension = int(self._model.config.hidden_size)

    def _select_device(self, torch: object) -> object:
        if self.device_request != "auto":
            return torch.device(self.device_request)
        if torch.cuda.is_available():
            return torch.device("cuda")
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")


def validate_embedding_matrix(
    embeddings: np.ndarray,
    *,
    expected_dim: int | None = None,
) -> np.ndarray:
    """Validate finite two-dimensional text embeddings."""

    matrix = np.asarray(embeddings, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("Embeddings must be a two-dimensional matrix.")
    if expected_dim is not None and matrix.shape[1] != expected_dim:
        raise ValueError(
            f"Embedding dimension {matrix.shape[1]} does not match expected {expected_dim}."
        )
    if not np.isfinite(matrix).all():
        raise ValueError("Embeddings contain NaN or infinite values.")
    return matrix


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize rows, leaving all-zero rows unchanged."""

    values = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return np.divide(values, np.where(norms == 0.0, 1.0, norms))


def _mean_pool_torch(last_hidden_state: object, attention_mask: object) -> object:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts
