import json
import subprocess

import pandas as pd
import pytest


def test_phase3c_text_embedding_workflow_writes_local_only_manifest(tmp_path):
    queries = pd.DataFrame(
        {
            "query_id": ["q1", "q2"],
            "query_text": ["altered mitochondrial organization", "lysosomal stress phenotype"],
        }
    )
    query_path = tmp_path / "queries.csv"
    queries.to_csv(query_path, index=False)
    out = tmp_path / "outputs" / "phase3c" / "text_embeddings"
    subprocess.run(
        [
            ".venv/bin/python",
            "scripts/build_phase3c_text_embeddings.py",
            "--queries",
            str(query_path),
            "--out",
            str(out),
            "--encoder",
            "fake",
        ],
        check=True,
    )
    manifest = json.loads(
        (out / "phase3c_text_embedding_manifest_public_safe.json").read_text()
    )
    assert manifest["n_queries"] == 2
    assert manifest["embedding_shape"] == [2, 16]
    serialized = json.dumps(manifest).lower()
    assert "altered mitochondrial" not in serialized
    assert ".npy" not in serialized


def test_phase3c_embedding_workflow_rejects_target_sequence(tmp_path):
    queries = pd.DataFrame(
        {
            "query_id": ["q1"],
            "query_text": ["aaaa-target-sequence"],
            "Metadata_target_sequence": ["aaaa-target-sequence"],
        }
    )
    query_path = tmp_path / "queries.csv"
    queries.to_csv(query_path, index=False)
    out = tmp_path / "outputs" / "phase3c" / "text_embeddings"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            [
                ".venv/bin/python",
                "scripts/build_phase3c_text_embeddings.py",
                "--queries",
                str(query_path),
                "--out",
                str(out),
                "--encoder",
                "fake",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
