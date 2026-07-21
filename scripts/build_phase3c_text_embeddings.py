#!/usr/bin/env python3
"""Build local-only Phase 3C text embeddings from identifier-stripped query text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.modeling.phase3c import validate_identifier_stripped_text  # noqa: E402
from perturb_lm.modeling.preprocessing import _validate_ignored_output_path  # noqa: E402
from perturb_lm.modeling.text_encoder import (  # noqa: E402
    BIOMEDBERT_SPEC,
    DeterministicFakeTextEncoder,
    FrozenBiomedicalTextEncoder,
    validate_embedding_matrix,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("outputs/phase3c/text_embeddings"))
    parser.add_argument("--text-column", default="query_text")
    parser.add_argument("--id-column", default="query_id")
    parser.add_argument("--encoder", choices=["fake", "biomedbert"], default="fake")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    _validate_ignored_output_path(args.out)
    queries = pd.read_csv(args.queries).sort_values(args.id_column, kind="mergesort")
    if args.text_column not in queries.columns or args.id_column not in queries.columns:
        raise ValueError("Query table must contain query ID and text columns.")
    validate_identifier_stripped_text(queries, queries, text_column=args.text_column)
    checksum = _query_checksum(queries, id_column=args.id_column, text_column=args.text_column)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "phase3c_text_embedding_manifest_public_safe.json"
    embeddings_path = args.out / "phase3c_text_embeddings.npy"
    if args.resume and manifest_path.exists() and embeddings_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous.get("query_selection_checksum") != checksum:
            raise ValueError("Cannot resume because query checksum changed.")
        print(f"Reusing existing embeddings under {args.out}")
        return

    if args.encoder == "fake":
        encoder = DeterministicFakeTextEncoder(seed=args.seed, embedding_dimension_value=16)
        encoder_payload = {
            "model_name": "deterministic_fake_text_encoder",
            "revision": "local-test-only",
            "embedding_dimension": encoder.embedding_dimension,
        }
    else:
        encoder = FrozenBiomedicalTextEncoder(
            batch_size=args.batch_size,
            device=args.device,
            cache_dir=args.cache_dir,
        )
        encoder_payload = BIOMEDBERT_SPEC.__dict__
    embeddings = encoder.encode(queries[args.text_column].astype(str).tolist())
    validate_embedding_matrix(embeddings, expected_dim=encoder.embedding_dimension)
    np.save(embeddings_path, embeddings)
    manifest = {
        "n_queries": int(len(queries)),
        "query_selection_checksum": checksum,
        "encoder": encoder_payload,
        "embedding_shape": [int(value) for value in embeddings.shape],
        "text_policy": "identifier_stripped_fields_only",
        "artifact_policy": "Embeddings are local-only outputs and must not be committed.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Wrote local-only Phase 3C text embeddings to {args.out}")


def _query_checksum(queries: pd.DataFrame, *, id_column: str, text_column: str) -> str:
    rows = [
        f"{row[id_column]}\t{row[text_column]}"
        for _, row in queries[[id_column, text_column]].astype(str).iterrows()
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
