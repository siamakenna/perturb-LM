"""Declarative planned families; importing this module never loads optional backends."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    identifier: str
    implementation: str
    optional_package: str | None = None


_SPECS = [
    ModelSpec("word_tfidf", "control", "sklearn:TfidfVectorizer:word", "available"),
    ModelSpec("character_tfidf", "control", "sklearn:TfidfVectorizer:char", "available"),
    ModelSpec("bm25", "control", "BM25", "available"),
    ModelSpec("random_ranking", "control", "numpy:random-ranking", "available"),
    ModelSpec("shuffled_query", "control", "numpy:query-permutation", "available"),
    ModelSpec("exact_gene_lookup", "control", "exact-gene-identity-control", "available"),
    ModelSpec(
        "biomedbert",
        "text",
        "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
        "planned",
        "transformers",
    ),
    ModelSpec("medcpt", "text", "ncbi/MedCPT-Query-Encoder", "planned", "transformers"),
    ModelSpec(
        "biolord_2023", "text", "FremyCompany/BioLORD-2023", "planned", "sentence_transformers"
    ),
    ModelSpec(
        "sapbert",
        "text",
        "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
        "planned",
        "transformers",
    ),
    ModelSpec(
        "biomedclip_text",
        "text",
        "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
        "planned",
        "open_clip",
    ),
    ModelSpec(
        "bge_base_en_v1_5", "text", "BAAI/bge-base-en-v1.5", "planned", "sentence_transformers"
    ),
    ModelSpec("cellprofiler", "morphology", "CellProfiler-features", "available"),
    ModelSpec("cellclip", "morphology", "CellCLIP", "planned"),
    ModelSpec("openphenom_s16", "morphology", "OpenPhenom-S/16", "planned"),
    ModelSpec("dinov2", "morphology", "DINOv2", "planned", "torch"),
    ModelSpec("rxrx_embeddings", "morphology", "RxRx-provided-embeddings", "available"),
    *[
        ModelSpec(name, "alignment", name, "available")
        for name in ("unaligned_cosine", "ridge", "pls", "cca")
    ],
    ModelSpec("mlp_projection", "alignment", "MLP-projection", "available"),
    ModelSpec("contrastive_projection", "alignment", "contrastive-projection-head", "available"),
]
REGISTRY = {spec.name: spec for spec in _SPECS}


@dataclass(frozen=True)
class ModelConfig:
    name: str
    revision: str

    def __post_init__(self):
        if self.name not in REGISTRY:
            raise ValueError(f"Unknown model family: {self.name}")
        if not self.revision or self.revision.lower() in {"main", "latest", "master"}:
            raise ValueError("Pin a model/code revision, or use pending-review for plan-only jobs")

    @property
    def spec(self) -> ModelSpec:
        return REGISTRY[self.name]


def require_backend(config: ModelConfig, weights_path: str | None = None) -> None:
    """Validate only; never resolve a model name through an online download API."""
    spec = config.spec
    if config.revision == "pending-review":
        raise ValueError(f"Pin an immutable reviewed revision for {spec.name} before execution")
    if spec.optional_package and find_spec(spec.optional_package) is None:
        raise ImportError(
            f"{spec.name} requires optional package {spec.optional_package}; "
            "install it explicitly in the execution environment"
        )
    if spec.family in {"text", "morphology"} and spec.implementation == "planned":
        if not weights_path or not Path(weights_path).exists():
            raise FileNotFoundError(
                f"Provide locally staged weights for {spec.name}; automatic downloads are disabled"
            )
    if spec.implementation == "planned":
        raise NotImplementedError(
            f"{spec.name} is registered but its reviewed Phase 2 backend is not implemented"
        )
