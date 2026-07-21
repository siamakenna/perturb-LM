from __future__ import annotations

import json

import numpy as np
import pandas as pd

from perturb_lm.data.jump import build_jump_profile_index
from perturb_lm.retrieval.index import build_sklearn_index, load_sklearn_index


def write_deterministic_jump_profile(data_root) -> None:
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv"
    pd.DataFrame(
        {
            "Metadata_Batch": ["batch-a", "batch-a", "batch-b", "batch-b"],
            "Metadata_Plate": ["plate-1", "plate-1", "plate-2", "plate-2"],
            "Metadata_Well": ["A01", "A02", "B01", "B02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-B", "BRD-B"],
            "Cells_AreaShape_Area": [1.0, 0.9, 0.0, 0.1],
            "Cytoplasm_Texture_InfoMeas": [0.0, 0.1, 1.0, 0.9],
            "Nuclei_Intensity_MeanIntensity": [0.8, 0.7, 0.2, 0.3],
        }
    ).to_csv(profile_path, index=False)


def test_jump_profile_index_save_load_is_deterministic(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    out_dir = tmp_path / "jump_pilot_index"
    write_deterministic_jump_profile(data_root)

    metadata = build_jump_profile_index(
        data_root,
        out_dir=out_dir,
        script_name="synthetic_test.py",
        command=["python", "synthetic_test.py"],
    )
    loaded = load_sklearn_index(out_dir)
    rebuilt = build_sklearn_index(loaded.embeddings)

    before_distances, before_indices = rebuilt.kneighbors(loaded.embeddings, n_neighbors=3)
    after_distances, after_indices = loaded.index.kneighbors(loaded.embeddings, n_neighbors=3)
    profile_metadata = pd.read_csv(out_dir / "profile_metadata.csv")
    manifest = json.loads((out_dir / "artifact_manifest.json").read_text())
    runtime = json.loads((out_dir / "runtime_log.json").read_text())

    np.testing.assert_array_equal(after_indices, before_indices)
    np.testing.assert_allclose(after_distances, before_distances, rtol=1e-12, atol=1e-12)
    assert loaded.metadata["number_of_rows"] == 4
    assert metadata["detected_numeric_feature_columns"] == [
        "Cells_AreaShape_Area",
        "Cytoplasm_Texture_InfoMeas",
        "Nuclei_Intensity_MeanIntensity",
    ]
    assert loaded.metadata["detected_numeric_feature_columns"] == metadata[
        "detected_numeric_feature_columns"
    ]
    assert profile_metadata["profile_id"].tolist() == loaded.id_mapping["profile_id"].tolist()
    assert profile_metadata["source_profile_row"].tolist() == [0, 1, 2, 3]
    assert loaded.id_mapping["row_index"].tolist() == [0, 1, 2, 3]
    assert manifest["row_count"] == 4
    assert manifest["feature_count"] == 3
    assert manifest["embedding_dimension"] == 3
    assert manifest["index_type"] == "sklearn-nearest-neighbors"
    assert manifest["distance_metric"] == "cosine"
    assert runtime["row_count"] == 4
    assert runtime["feature_count"] == 3

