from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from perturb_lm.sklearn_api import (
    AdapterConfig,
    BM25Retriever,
    LocalDatasetAdapter,
    LocalModelEmbedder,
    MetricEvaluator,
    RelevanceContract,
    SplitSpec,
    aggregate_results,
    asset_catalog,
    fit_alignment_stage,
    save_embedding_stage,
)
from perturb_lm.sklearn_api.datasets import DatasetManifest, file_checksum
from perturb_lm.sklearn_api.execution import completion_valid


def write_normalized(tmp_path, dataset="synthetic"):
    frame = pd.DataFrame(
        {
            "record_id": ["r1", "r2", "r3", "r4"],
            "dataset": [dataset] * 4,
            "source": ["s1"] * 4,
            "batch": ["b1"] * 4,
            "plate": ["p1", "p1", "p2", "p2"],
            "well": ["A01", "A02", "A01", "A02"],
            "treatment": ["t1", "t1", "t2", "t2"],
            "perturbation": ["x"] * 4,
            "gene": ["G1", "G1", "G2", "G2"],
            "compound": ["C1", "C1", "C2", "C2"],
            "replicate": ["1", "2", "1", "2"],
            "image_id": ["i1", "i2", "i3", "i4"],
            "profile_id": ["pr1", "pr2", "pr3", "pr4"],
            "split": ["train", "train", "test", "test"],
            "Cells_Area": [1, 2, 3, 4],
            "Cells_Texture": [4, 3, 2, 1],
        }
    )
    path = tmp_path / f"{dataset}.csv"
    frame.to_csv(path, index=False)
    manifest = DatasetManifest(
        dataset, "fixture-v1", path.name, file_checksum(path), synthetic=True
    )
    return frame, manifest


def test_relevance_contracts_are_machine_readable_and_guarded():
    payload = yaml.safe_load(Path("configs/benchmark_v2/relevance_contracts.yaml").read_text())
    contracts = {
        name: RelevanceContract.from_dict(value) for name, value in payload["contracts"].items()
    }
    assert contracts["M0_GENE_AWARE_V1"].positive_rule == "exact_treatment"
    with pytest.raises(ValueError, match="scientific_approval"):
        contracts["M1_BIOLOGICAL_CONTEXT"].require_execution(synthetic=False)
    with pytest.raises(ValueError, match="mapping provenance"):
        RelevanceContract(
            "transfer",
            "1",
            "treatment",
            "exact_gene_context",
            ("gene", "perturbation_type", "species"),
            "gene",
            replicate_handling="mean_scores_after_filtering",
            cross_dataset=True,
        )


def test_custom_relevance_contract_does_not_require_treatment_column():
    contract = RelevanceContract(
        "gene-context",
        "1",
        "treatment",
        "exact_gene_context",
        ("gene", "perturbation_type", "species"),
        "gene-context-v1",
        replicate_handling="mean_scores_after_filtering",
        exclusions=(),
        approval="synthetic",
    )
    queries = pd.DataFrame(
        {
            "query_id": ["q1"],
            "record_id": ["query-record"],
            "gene": ["G1"],
            "perturbation_type": ["KO"],
            "species": ["human"],
        }
    )
    candidates = pd.DataFrame(
        {
            "record_id": ["r1", "r2"],
            "gene": ["G1", "G2"],
            "perturbation_type": ["KO", "KO"],
            "species": ["human", "human"],
        }
    )
    result = MetricEvaluator(retrieval_unit="treatment", relevance=contract).evaluate(
        np.array([[0.9, 0.1]]), queries, candidates, SplitSpec(exclude=())
    )
    assert result.summary["n_evaluable_queries"] == 1
    assert result.per_query.loc[0, "n_positives"] == 1


@pytest.mark.parametrize(
    "dataset",
    ["synthetic", "CPJUMP1", "JUMP_cpg0016", "JUMP_cpg0000", "JUMP_cpg0002", "RxRx1", "RxRx19a"],
)
def test_normalized_adapter_schema_status_and_checksums(tmp_path, dataset):
    actual_dataset = "synthetic" if dataset == "synthetic" else dataset
    frame, manifest = write_normalized(tmp_path, actual_dataset)
    adapter = LocalDatasetAdapter(
        manifest, tmp_path, AdapterConfig(feature_columns=("Cells_Area", "Cells_Texture"))
    )
    result = adapter.validate(include_representations=True)
    assert result["status"] == "schema_tested"
    assert result["representation_shape"] == [4, 2]
    assert adapter.load()["well"].tolist() == ["A01", "A02", "A01", "A02"]


def test_adapter_rejects_duplicate_wells_and_invented_mappings(tmp_path):
    frame, manifest = write_normalized(tmp_path)
    frame.loc[1, "well"] = "A01"
    frame.to_csv(tmp_path / manifest.metadata_path, index=False)
    manifest = DatasetManifest(
        manifest.dataset,
        manifest.version,
        manifest.metadata_path,
        file_checksum(tmp_path / manifest.metadata_path),
        synthetic=True,
    )
    with pytest.raises(ValueError, match="Duplicate physical well"):
        LocalDatasetAdapter(manifest, tmp_path, AdapterConfig(record_unit="well")).load()
    with pytest.raises(ValueError, match="Configured column missing"):
        LocalDatasetAdapter(manifest, tmp_path, AdapterConfig(columns={"gene": "unknown"})).load()


def test_bm25_is_seedless_deterministic_and_has_sklearn_params():
    model = BM25Retriever(k1=1.2, b=0.6).fit(
        ["gene knockout", "compound treatment", "cell control"]
    )
    first = model.predict(["gene knockout"])
    assert np.array_equal(first, model.predict(["gene knockout"]))
    assert first.argmax() == 0
    assert model.get_params()["k1"] == 1.2


def test_neural_alignment_fit_checkpoint_and_degenerate_guards(tmp_path):
    rng = np.random.default_rng(10)
    text, morphology = rng.normal(size=(12, 4)), rng.normal(size=(12, 3))
    groups = np.array([f"g{i // 2}" for i in range(12)])
    checkpoint = tmp_path / "projection.npz"
    model = fit_alignment_stage(
        text,
        morphology,
        method="mlp_projection",
        epochs=4,
        hidden_dim=5,
        learning_rate=0.005,
        random_state=3,
        output=tmp_path / "projection.pkl",
    )
    assert model.predict(text[:2]).shape == (2, 3)
    contrastive = fit_alignment_stage(
        text,
        morphology,
        method="contrastive_projection",
        epochs=3,
        hidden_dim=5,
        learning_rate=0.005,
        temperature=0.2,
        random_state=3,
        group_ids=groups,
    )
    assert contrastive.predict(text[:2]).shape == (2, 3)
    from perturb_lm.sklearn_api.neural import NeuralProjection

    NeuralProjection(epochs=2, hidden_dim=4).fit(text, morphology, checkpoint=checkpoint)
    resumed = NeuralProjection(epochs=4, hidden_dim=4).fit(text, morphology, checkpoint=checkpoint)
    assert resumed.state_metadata_["input_dimension"] == 4
    with pytest.raises(ValueError, match="Degenerate"):
        NeuralProjection().fit(np.ones((4, 2)), morphology[:4])
    with pytest.raises(ValueError, match="Contrastive"):
        NeuralProjection(objective="contrastive").fit(text, morphology)


def test_embedding_cache_mock_boundary_and_partial_rejection(tmp_path, monkeypatch):
    spec = asset_catalog()["biomedbert"]
    asset = tmp_path / "asset"
    asset.mkdir()
    weight = asset / "weights.bin"
    weight.write_bytes(b"fixture")
    (asset / "asset.json").write_text(
        json.dumps(
            {
                "identifier": spec.identifier,
                "revision": spec.revision,
                "complete": True,
                "checksums": {"weights.bin": file_checksum(weight)},
            }
        )
    )
    calls = {"count": 0}

    def fake_backend(*args, **kwargs):
        calls["count"] += 1
        return lambda batch: np.ones((len(batch), spec.dimension), dtype=np.float32)

    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.load_backend", fake_backend)
    embedder = LocalModelEmbedder(spec, asset, tmp_path / "cache", batch_size=2).fit(
        ["a", "b", "c"]
    )
    first = embedder.transform(["a", "b", "c"])
    second = embedder.transform(["a", "b", "c"])
    assert first.shape == (3, 768) and np.array_equal(first, second) and calls["count"] == 1
    cache = next((tmp_path / "cache").iterdir())
    (cache / "embeddings.npy").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Corrupt"):
        embedder.transform(["a", "b", "c"])


def test_atomic_embedding_worker_and_aggregate_bundle(tmp_path):
    output = save_embedding_stage(
        np.eye(3), ["a", "b", "c"], tmp_path / "embeddings", {"run_id": "r"}
    )
    assert (output / "complete.json").exists()
    per_query = pd.DataFrame(
        {
            "query_id": ["q1", "q2"],
            "evaluable": [True, False],
            "average_precision": [0.5, np.nan],
            "hit_at_1": [1.0, np.nan],
            "recall_at_1": [0.5, np.nan],
        }
    )
    exclusions = pd.DataFrame({"query_id": ["q2"], "reason": ["no_positive_after_filtering"]})
    bundle = tmp_path / "results"
    summary = aggregate_results(
        per_query, exclusions=exclusions, provenance={"run_id": "r"}, output=bundle
    )
    assert summary["n_evaluable_queries"] == 1
    assert (bundle / "complete.json").exists()
    assert completion_valid(bundle, "wrong-run") is False
