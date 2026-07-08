from __future__ import annotations

import json

from perturb_lm.engineering.artifacts import build_artifact_manifest, write_artifact_manifest


def test_artifact_manifest_records_sizes_without_copying_data(tmp_path) -> None:
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "index_metadata.json"
    input_path.write_text("secret,row,data\n")
    output_path.write_text('{"rows": 1}\n')

    manifest = build_artifact_manifest(
        artifact_type="unit_test_artifact",
        input_paths=[input_path],
        output_paths=[output_path],
        dataset="synthetic",
        row_count=1,
        feature_count=2,
        embedding_dimension=2,
        index_type="sklearn-nearest-neighbors",
        distance_metric="cosine",
        warnings=["synthetic warning"],
        notes=["metadata only"],
        script_name="build_test.py",
        command=["python", "build_test.py", "--out", str(tmp_path)],
        repo_root=tmp_path,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    manifest_path = write_artifact_manifest(tmp_path / "artifact_manifest.json", manifest)
    saved = json.loads(manifest_path.read_text())

    assert saved["schema_version"] == "1.0"
    assert saved["artifact_type"] == "unit_test_artifact"
    assert saved["script_name"] == "build_test.py"
    assert saved["dataset"] == "synthetic"
    assert saved["row_count"] == 1
    assert saved["feature_count"] == 2
    assert saved["embedding_dimension"] == 2
    assert saved["index_type"] == "sklearn-nearest-neighbors"
    assert saved["distance_metric"] == "cosine"
    assert saved["input_paths"] == [str(input_path)]
    assert saved["output_paths"] == [str(output_path)]
    assert saved["input_file_sizes"][str(input_path)] == input_path.stat().st_size
    assert saved["output_file_sizes"][str(output_path)] == output_path.stat().st_size
    assert "git_commit" in saved
    assert "git_branch" in saved
    assert isinstance(saved["git_dirty"], bool) or saved["git_dirty"] is None
    assert "secret,row,data" not in manifest_path.read_text()


def test_artifact_manifest_uses_none_for_missing_file_sizes(tmp_path) -> None:
    missing = tmp_path / "missing.npy"

    manifest = build_artifact_manifest(
        artifact_type="missing_size_check",
        output_paths=[missing],
        repo_root=tmp_path,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert manifest["output_file_sizes"][str(missing)] is None
