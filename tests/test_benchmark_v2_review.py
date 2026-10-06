"""Regression coverage for the final scientific/provenance review; synthetic only."""

import json
import os
import pickle
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.exceptions import NotFittedError

from perturb_lm.sklearn_api import (
    AdapterConfig,
    AlignmentEstimator,
    BenchmarkPipeline,
    BM25Retriever,
    DatasetManifest,
    LocalDatasetAdapter,
    LocalModelEmbedder,
    ManifestDatasetAdapter,
    MetricEvaluator,
    QueryBootstrap,
    QueryPolicyTransformer,
    RelevanceContract,
    SplitSpec,
    aggregate_results,
    asset_catalog,
    evaluate_retrieval_stage,
    save_embedding_stage,
)
from perturb_lm.sklearn_api.datasets import file_checksum
from perturb_lm.sklearn_api.execution import (
    ROOT,
    completion_valid,
    frozen_check,
    run_job,
    slurm_script,
)
from perturb_lm.sklearn_api.model_assets import load_backend, validate_asset
from perturb_lm.sklearn_api.neural import NeuralProjection
from perturb_lm.sklearn_api.planning import (
    build_plan,
    code_identity,
    load_config,
    load_relevance_contracts,
)


@pytest.fixture
def records():
    return ManifestDatasetAdapter(
        load_config(ROOT / "configs/benchmark_v2/synthetic_smoke.yaml")[0].dataset, ROOT
    ).load()


def gene_contract(**kwargs):
    return RelevanceContract(
        "gene-context",
        "1",
        "treatment",
        "exact_gene_context",
        ("gene", "perturbation_type", "species"),
        "gene-context-v1",
        replicate_handling="mean_scores_after_filtering",
        approval="synthetic",
        **kwargs,
    )


def test_pipeline_custom_identity_training_groups_and_serialization(records):
    frame = records.drop(columns="treatment").assign(perturbation_type="KO", species="human")
    train, test = frame[frame.split == "train"], frame[frame.split == "test"]
    features = ["Cells_Area", "Cells_Texture"]
    contract = gene_contract()
    pipeline = BenchmarkPipeline(
        evaluator=MetricEvaluator(retrieval_unit="treatment", relevance=contract),
        synthetic=True,
        alignment=AlignmentEstimator(method="contrastive_projection", epochs=2),
    )
    clone(pipeline).fit(
        train, train[features].astype(float), gallery=test, gallery_y=test[features].astype(float)
    )
    pipeline.fit(
        train, train[features].astype(float), gallery=test, gallery_y=test[features].astype(float)
    )
    assert pipeline.evaluate(test).summary["n_evaluable_queries"] == len(test)
    assert np.array_equal(
        pipeline.predict(test), pickle.loads(pickle.dumps(pipeline)).predict(test)
    )
    with pytest.raises(ValueError, match="scientific_approval"):
        clone(pipeline).set_params(synthetic=False).fit(
            train, train[features], gallery=test, gallery_y=test[features]
        )
    with pytest.raises(ValueError):
        pipeline.fit(train, train[features], gallery=train, gallery_y=train[features])
    with pytest.raises(NotFittedError):
        pipeline.predict(test)


def test_custom_held_out_identity_is_checked_without_treatment(records):
    frame = records.drop(columns="treatment").assign(perturbation_type="KO", species="human")
    train, test = frame[frame.split == "train"], frame[frame.split == "test"]
    with pytest.raises(ValueError, match="leakage"):
        gene_contract().validate_split(train, test, SplitSpec("held_out_treatment"))
    gene_contract().validate_split(
        train, test.assign(gene="new_gene"), SplitSpec("held_out_treatment")
    )


def test_record_rendering_is_independent_of_relevance(records):
    result = QueryPolicyTransformer().fit_transform(records.drop(columns="treatment"))
    assert len(result) == len(records)


def test_split_checks_sites_groups_and_scoped_gene(records):
    train = records.iloc[:1].copy()
    test = train.assign(record_id="different_site", treatment="different_treatment", well="a1")
    train["well"] = "A01"
    with pytest.raises(ValueError, match="physical well"):
        SplitSpec("held_out_treatment").validate(train, test)
    train, test = records[records.split == "train"].copy(), records[records.split == "test"].copy()
    train["replicate_group"] = "replicate-group-a"
    test["replicate_group"] = "replicate-group-a"
    with pytest.raises(ValueError, match="replicate group"):
        SplitSpec(group_fields=("replicate_group",)).validate(train, test)
    with pytest.raises(ValueError, match="leakage"):
        SplitSpec("held_out_gene").validate(
            train.assign(species="human"), test.assign(species="human")
        )


def test_retrieval_worker_checks_train_against_both_heldout_populations(records):
    train, test = records[records.split == "train"], records[records.split == "test"]
    queries = QueryPolicyTransformer().fit_transform(test)
    contract = load_relevance_contracts()["M0_IDENTITY_FREE_V2"]
    kwargs = dict(contract=contract, train_metadata=train, synthetic=True)
    result = evaluate_retrieval_stage(np.eye(len(test)), queries, test, SplitSpec(), **kwargs)
    assert result.summary["n_queries"] == len(test)
    with pytest.raises(ValueError, match="scientific_approval"):
        evaluate_retrieval_stage(
            np.eye(len(test)), queries, test, SplitSpec(), **{**kwargs, "synthetic": False}
        )
    with pytest.raises(ValueError, match="leakage"):
        evaluate_retrieval_stage(
            np.eye(len(test)), queries, test, SplitSpec(), **{**kwargs, "train_metadata": test}
        )


def test_nontransfer_identity_is_dataset_scoped():
    contract = gene_contract()
    row = pd.Series(dict(dataset="a", gene="G", perturbation_type="KO", species="human"))
    other = row.copy()
    other["dataset"] = "b"
    assert contract.identity(row) != contract.identity(other)
    transfer = replace(contract, cross_dataset=True, mapping_provenance="reviewed-fixture-map")
    other = row.copy()
    other["dataset"] = "b"
    assert transfer.identity(row) == transfer.identity(other)


def test_well_aliases_are_duplicate_candidates(records):
    candidates = records.iloc[:2].copy()
    candidates["well"] = ["A1", "a01"]
    query = records.iloc[-1:].assign(query_id="q")
    with pytest.raises(ValueError, match="Aggregate"):
        MetricEvaluator().evaluate([[1, 0]], query, candidates, SplitSpec(exclude=()))


def test_unrelated_worktree_changes_do_not_change_identity(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (tmp_path / "pyproject.toml").write_text("fixture")
    for file in ("src/perturb_lm/retrieval/text_profile.py", "src/perturb_lm/modeling/phase3c.py"):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    for folder in (
        "src/perturb_lm/sklearn_api",
        "configs/benchmark_v2",
        "slurm/benchmark_v2",
        "tests/fixtures/benchmark_v2",
    ):
        (tmp_path / folder).mkdir(parents=True)
    before = code_identity(tmp_path)
    (tmp_path / "unrelated-notes.txt").write_text("user note")
    assert code_identity(tmp_path) == before
    jobs = load_config(ROOT / "configs/benchmark_v2/synthetic_smoke.yaml")
    assert build_plan(jobs, {**before, "dirty_worktree": True}) == build_plan(
        jobs, {**before, "dirty_worktree": False}
    )
    (tmp_path / "src/perturb_lm/sklearn_api/new.py").write_text("change")
    assert code_identity(tmp_path)["source_sha256"] != before["source_sha256"]


def test_plans_bind_relevance_and_worker_uses_it(tmp_path, monkeypatch):
    jobs = load_config(ROOT / "configs/benchmark_v2/synthetic_smoke.yaml")
    contracts = load_relevance_contracts()
    contracts["M0_IDENTITY_FREE_V2"] = gene_contract()
    for module in ("planning", "execution"):
        monkeypatch.setattr(
            f"perturb_lm.sklearn_api.{module}.load_relevance_contracts", lambda: contracts
        )
    plan = build_plan(jobs, code_identity(ROOT))
    assert plan[0]["relevance"]["positive_rule"] == "exact_gene_context"
    # Fixture lacks required species/type. Old worker silently scored treatment instead.
    with pytest.raises(ValueError, match="Missing relevance fields"):
        run_job(plan[0], tmp_path)
    assert not completion_valid(tmp_path / plan[0]["run_id"], plan[0]["run_id"])
    assert not (tmp_path / plan[0]["run_id"] / ".running").exists()


def test_resume_rechecks_dependency_and_frozen_inputs(tmp_path, monkeypatch):
    jobs = load_config(ROOT / "configs/benchmark_v2/synthetic_smoke.yaml")
    plan = build_plan(jobs, code_identity(ROOT))
    for row in plan[:2]:
        run_job(row, tmp_path)
    marker = tmp_path / plan[1]["run_id"] / "complete.json"
    manifest = json.loads(marker.read_text())
    manifest["configuration"]["seed"] += 1
    marker.write_text(json.dumps(manifest))
    assert not completion_valid(marker.parent, plan[1]["run_id"])
    run_job(plan[1], tmp_path)
    assert completion_valid(marker.parent, plan[1]["run_id"])
    (tmp_path / plan[0]["run_id"] / "arrays.npz").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Dependency"):
        run_job(plan[1], tmp_path)
    frozen = build_plan(
        load_config(ROOT / "configs/benchmark_v2/cpjump1_regression.yaml"), code_identity(ROOT)
    )[0]
    run_job(frozen, tmp_path)

    def fail():
        raise ValueError("Frozen reference changed")

    monkeypatch.setattr("perturb_lm.sklearn_api.execution.frozen_check", fail)
    with pytest.raises(ValueError, match="Frozen reference"):
        run_job(frozen, tmp_path)


def test_bootstrap_and_aggregation_use_evaluable_intersection(tmp_path):
    candidate = pd.DataFrame(
        dict(
            query_id=["a", "b", "c"],
            evaluable=[True, False, True],
            average_precision=[1.0, 1.0, 0.7],
        )
    )
    baseline = pd.DataFrame(
        dict(
            query_id=["c", "a", "b"],
            evaluable=[False, True, True],
            average_precision=[0.2, 0.4, 0.5],
        )
    )
    bootstrap = QueryBootstrap(n_resamples=20)
    result = bootstrap.evaluate(candidate, baseline)
    assert result["n_evaluable_queries"] == 1
    assert result["estimate"] == pytest.approx(0.6)
    summary = aggregate_results(
        candidate,
        exclusions=pd.DataFrame(columns=["query_id", "reason"]),
        provenance={"run_id": "pair"},
        output=tmp_path / "pair",
        baseline=baseline,
        bootstrap=bootstrap,
    )
    assert summary["paired_difference"] == pytest.approx(0.6)
    assert summary["n_evaluable_pairs"] == 1
    assert completion_valid(tmp_path / "pair", "pair")
    (tmp_path / "pair" / "per_query.csv").write_text("corrupt")
    assert not completion_valid(tmp_path / "pair", "pair")
    summary = aggregate_results(
        candidate,
        exclusions=pd.DataFrame(columns=["query_id", "reason"]),
        provenance={},
        output=tmp_path / "empty",
        baseline=baseline.assign(evaluable=False),
        bootstrap=bootstrap,
    )
    assert summary["paired_difference"] is None and summary["n_evaluable_pairs"] == 0


def staged_asset(tmp_path, spec):
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "fixture.bin").write_bytes(b"synthetic")
    (asset / "asset.json").write_text(
        json.dumps(
            dict(
                identifier=spec.identifier,
                revision=spec.revision,
                complete=True,
                checksums={"fixture.bin": file_checksum(asset / "fixture.bin")},
            )
        )
    )
    return asset


def test_model_refit_pickle_and_asset_changes(tmp_path, monkeypatch):
    spec = asset_catalog()["biomedbert"]
    asset = staged_asset(tmp_path, spec)
    calls = []

    def backend(*args):
        calls.append(1)
        return lambda batch: np.ones((len(batch), spec.dimension))

    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.load_backend", backend)
    embedder = LocalModelEmbedder(spec, asset).fit(["a"])
    assert clone(embedder).spec == spec
    expected = embedder.transform(["a"])
    restored = pickle.loads(pickle.dumps(embedder))
    assert np.array_equal(restored.transform(["a"]), expected)
    embedder.fit(["a"]).transform(["a"])
    assert len(calls) == 3
    (asset / "fixture.bin").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="checksum"):
        embedder.transform(["a"])


def test_asset_manifest_must_cover_configs(tmp_path):
    spec = asset_catalog()["biomedbert"]
    asset = staged_asset(tmp_path, spec)
    (asset / "config.json").write_text("{}")
    with pytest.raises(ValueError, match="every staged file"):
        validate_asset(asset, spec)


@pytest.mark.parametrize("name", ["cellclip", "openphenom_s16", "biomedclip_text"])
def test_unreviewed_backend_does_not_import_code(name, monkeypatch, tmp_path):
    def fail(name):
        raise AssertionError("No optional code may be loaded before backend review")

    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.optional_import", fail)
    with pytest.raises(NotImplementedError, match="needs_backend_review"):
        load_backend(asset_catalog()[name], tmp_path, "cpu", True)


def test_numeric_cache_hash_includes_dtype(tmp_path, monkeypatch):
    spec = replace(asset_catalog()["dinov2"], name="synthetic_image", dimension=2, input_shape=(1,))
    asset = staged_asset(tmp_path, spec)
    calls = []

    def backend(*args):
        def encode(batch):
            calls.append(1)
            return np.tile([1.0, 2.0], (len(batch), 1))

        return encode

    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.load_backend", backend)
    floats = np.array([[1]], dtype=np.float32)
    integers = floats.view(np.int32)
    assert floats.tobytes() == integers.tobytes()
    model = LocalModelEmbedder(spec, asset, tmp_path / "cache").fit(floats)
    model.transform(floats)
    model.transform(integers)
    assert len(calls) == 2


def test_neural_resume_matches_uninterrupted_training_and_rejects_missing_groups(tmp_path):
    rng = np.random.default_rng(10)
    x, y = rng.normal(size=(8, 3)), rng.normal(size=(8, 2))
    checkpoint = tmp_path / "neural.npz"
    NeuralProjection(epochs=2).fit(x, y, checkpoint=checkpoint)
    resumed = NeuralProjection(epochs=4).fit(x, y, checkpoint=checkpoint)
    direct = NeuralProjection(epochs=4).fit(x, y)
    assert np.array_equal(resumed.predict(x), direct.predict(x))
    with np.load(checkpoint, allow_pickle=False) as saved:
        tampered = dict(saved)
    tampered["w0"] = tampered["w0"] + 1
    np.savez(checkpoint, **tampered)
    with pytest.raises(ValueError, match="checksum"):
        NeuralProjection(epochs=4).fit(x, y, checkpoint=checkpoint)
    with pytest.raises(ValueError, match="groups"):
        NeuralProjection(objective="contrastive").fit(x, y, group_ids=[None] + list(range(7)))


def test_empty_bm25_document_and_embedding_integrity(tmp_path):
    scores = BM25Retriever(b=1).fit(["", "cell"]).predict(["cell"])
    assert np.isfinite(scores).all() and scores[0, 0] == 0
    folder = save_embedding_stage(np.eye(2), ["a", "b"], tmp_path / "emb", {"run_id": "emb"})
    assert completion_valid(folder, "emb")
    (folder / "embeddings.npz").write_bytes(b"bad")
    assert not completion_valid(folder, "emb")


def test_frozen_files_still_match():
    assert set(frozen_check()["files"].values()) <= {"checksum_verified", "unavailable"}


@pytest.mark.parametrize("pooling,expected", [("mean", [2.0, 4.0]), ("cls", [1.0, 3.0])])
def test_hf_backend_offline_loading_masked_pooling_and_batching(
    pooling, expected, tmp_path, monkeypatch
):
    # Minimal numerical tensor shim: exercise adapter code without installing Torch or weights.
    class Tensor(np.ndarray):
        def __new__(cls, value):
            return np.asarray(value).view(cls)

        def to(self, device):
            return self

        def unsqueeze(self, axis):
            return Tensor(np.expand_dims(self, axis))

        def sum(self, dim=None, **kwargs):
            return Tensor(np.asarray(self).sum(axis=dim, **kwargs))

        def clamp(self, min):
            return Tensor(np.maximum(self, min))

        def detach(self):
            return self

        def float(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.asarray(self)

    lengths = []

    class Tokenizer:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert path == str(tmp_path / "asset") and kwargs == {"local_files_only": True}
            return cls()

        def __call__(self, batch, **kwargs):
            assert kwargs["truncation"] and kwargs["max_length"] == 512
            lengths.append(len(batch))
            return {"attention_mask": Tensor([[1, 1, 0]] * len(batch))}

    class Model:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert path == str(tmp_path / "asset")
            assert kwargs == {"local_files_only": True, "trust_remote_code": False}
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, attention_mask):
            return SimpleNamespace(
                last_hidden_state=Tensor([[[1, 3], [3, 5], [900, 900]]] * len(attention_mask))
            )

    modules = {
        "torch": SimpleNamespace(inference_mode=nullcontext),
        "transformers": SimpleNamespace(AutoModel=Model, AutoTokenizer=Tokenizer),
    }
    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.optional_import", modules.__getitem__)
    spec = replace(asset_catalog()["biomedbert"], dimension=2, pooling=pooling, normalize=False)
    asset = staged_asset(tmp_path, spec)
    result = LocalModelEmbedder(spec, asset, batch_size=2).fit_transform(["a", "b", "c"])
    assert lengths == [2, 1]
    assert np.array_equal(result, [expected] * 3)


def test_generated_slurm_script_preserves_quoted_paths_and_dependencies(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    captured = tmp_path / "calls.jsonl"
    stub = bindir / "sbatch"
    (bindir / "python").symlink_to(sys.executable)
    stub.write_text(
        "#!/usr/bin/env python\n"
        "import json, os, sys\n"
        "with open(os.environ['CAPTURE'], 'a+') as f:\n"
        "    f.seek(0)\n"
        "    count = len(f.readlines())\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print(str(100 + count) + ';fixture-cluster')\n"
    )
    stub.chmod(0o755)
    plan = build_plan(
        load_config(ROOT / "configs/benchmark_v2/synthetic_smoke.yaml"), code_identity(ROOT)
    )
    logs = tmp_path / "logs with 'quotes' $(touch unwanted)"
    script = tmp_path / "submit.sh"
    script.write_text(
        slurm_script(plan, tmp_path / "plan with spaces.json", tmp_path / "runs", logs)
    )
    subprocess.run(["/bin/bash", "-n", str(script)], check=True)
    subprocess.run(
        ["/bin/bash", str(script)],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "CAPTURE": str(captured)},
        check=True,
    )
    calls = [json.loads(line) for line in captured.read_text().splitlines()]
    assert len(calls) == 4
    assert f"--output={logs}/%x-%A_%a.out" in calls[0]
    assert "--dependency=afterok:100" in calls[1]
    assert "--dependency=afterok:102" in calls[3]
    assert not (tmp_path / "unwanted").exists()


def test_malformed_completion_markers_are_not_valid(tmp_path):
    (tmp_path / "complete.json").write_text("[]")
    assert not completion_valid(tmp_path, "id")
    (tmp_path / "complete.json").write_text('{"run_id":"id","output_checksums":["a"]}')
    assert not completion_valid(tmp_path, "id")


@pytest.mark.parametrize(
    "dataset,id_column,treatment_column",
    [
        ("CPJUMP1", "profile_id", "Metadata_broad_sample"),
        ("RxRx1", "site_id", "sirna"),
        ("RxRx19a", "site_id", "treatment_id"),
    ],
)
def test_raw_adapter_preserves_ids_and_aligns_shuffled_representation_cache(
    tmp_path, dataset, id_column, treatment_column
):
    metadata = tmp_path / "raw.csv"
    pd.DataFrame(
        {id_column: ["001", "002"], treatment_column: ["0007", "0008"], "split": ["train", "test"]}
    ).to_csv(metadata, index=False)
    cache = tmp_path / "representation.npz"
    np.savez(cache, record_ids=["002", "001"], embeddings=[[20.0, 21.0], [10.0, 11.0]])
    manifest = DatasetManifest(
        dataset,
        "synthetic-raw",
        metadata.name,
        file_checksum(metadata),
        representation_path=cache.name,
        representation_sha256=file_checksum(cache),
        synthetic=True,
    )
    adapter = LocalDatasetAdapter(manifest, tmp_path, AdapterConfig())
    frame = adapter.load()
    assert frame.record_id.tolist() == ["001", "002"]
    assert frame.treatment.tolist() == ["0007", "0008"]
    assert frame[f"original::{id_column}"].tolist() == ["001", "002"]
    assert adapter.representations(frame).tolist() == [[10.0, 11.0], [20.0, 21.0]]
    assert adapter.validate(True)["status"] == "schema_tested"
