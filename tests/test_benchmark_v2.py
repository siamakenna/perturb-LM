"""Phase 1 contracts use only tiny synthetic fixtures and read-only frozen checks."""

from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.base import clone
from sklearn.exceptions import NotFittedError

from perturb_lm.retrieval.text_profile import (
    IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES,
    _tfidf_scores,
    build_metadata_text_queries,
)
from perturb_lm.sklearn_api import (
    POLICIES,
    REGISTRY,
    AlignmentEstimator,
    BenchmarkPipeline,
    CPJUMP1MetadataAdapter,
    DatasetManifest,
    ManifestDatasetAdapter,
    MetricEvaluator,
    ModelConfig,
    MorphologyEmbedder,
    QueryBootstrap,
    QueryPolicyTransformer,
    RetrievalEstimator,
    SplitSpec,
    TfidfTextEmbedder,
    audit_text,
)
from perturb_lm.sklearn_api.datasets import DATASETS, file_checksum, validate_records
from perturb_lm.sklearn_api.execution import (
    ROOT,
    completion_valid,
    frozen_check,
    run_job,
    slurm_commands,
    slurm_script,
)
from perturb_lm.sklearn_api.planning import (
    Resources,
    build_plan,
    canonical_hash,
    code_identity,
    load_config,
    write_plan,
)
from perturb_lm.sklearn_api.registry import require_backend

CONFIG = ROOT / "configs/benchmark_v2/synthetic_smoke.yaml"


@pytest.fixture
def records():
    return ManifestDatasetAdapter(load_config(CONFIG)[0].dataset, ROOT).load()


@pytest.mark.parametrize(
    "estimator",
    [
        QueryPolicyTransformer(),
        TfidfTextEmbedder(),
        TfidfTextEmbedder("char", (2, 4)),
        MorphologyEmbedder(),
        AlignmentEstimator(),
        RetrievalEstimator(),
        MetricEvaluator(),
        QueryBootstrap(),
        BenchmarkPipeline(alignment=AlignmentEstimator(alpha=2)),
    ],
)
def test_clone_and_parameters(estimator):
    copied = clone(estimator)
    assert copied is not estimator
    assert copied.get_params(deep=False).keys() == estimator.get_params(deep=False).keys()
    if isinstance(copied, BenchmarkPipeline):
        copied.set_params(alignment__alpha=3)
        assert copied.get_params()["alignment__alpha"] == 3
        assert estimator.alignment.alpha == 2


@pytest.mark.parametrize("policy", POLICIES)
def test_query_records_are_audited_stable_and_keep_identity_separate(records, policy):
    transformer = QueryPolicyTransformer(policy).fit(records)
    first = transformer.transform(records)
    second = transformer.transform(records.sample(frac=1, random_state=9))
    assert set(first.query_id) == set(second.query_id)
    assert first.leakage_audit.map(lambda audit: audit["passed"]).all()
    assert set(first.policy_version) == {POLICIES[policy].version}
    assert first.biological_identity.iloc[0]["treatment"] == "treatment_0"
    assert "treatment_0" not in first.rendered_text.iloc[0]
    if policy != "M0_GENE_AWARE_V1":
        assert "GENE_0" not in first.rendered_text.iloc[0]
    if policy == "M5_LEAKAGE_CONTROL":
        assert set(first.rendered_text) == {"cellular perturbation"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("gene", "TP53"),
        ("gene", "X"),
        ("Metadata_target_sequence", "ACGTACGT"),
        ("plate", "P1"),
        ("well", "A01"),
        ("compound", "BRD-123"),
        ("source_profile_row", "2"),
        ("gene_aliases", ["alias1", "alias2"]),
    ],
)
def test_leakage_audit_short_identifiers_aliases_and_global_universe(field, value):
    universe = pd.DataFrame([{field: value}])
    identifier = value[-1] if isinstance(value, list) else value
    with pytest.raises(ValueError, match="Prohibited identifier"):
        audit_text(
            f"cells with {identifier.lower()} response", POLICIES["M0_IDENTITY_FREE_V2"], universe
        )
    audit_text("generic phenotype", POLICIES["M0_IDENTITY_FREE_V2"], universe)


def test_contaminated_allowed_fields_fail_before_encoding(records):
    corrupted = records.copy()
    corrupted.loc[0, "Metadata_pert_type"] = records.gene.iloc[-1]
    with pytest.raises(ValueError, match="Prohibited identifier"):
        QueryPolicyTransformer().fit_transform(corrupted)
    with pytest.raises(ValueError, match="annotation_provenance"):
        QueryPolicyTransformer("M1_BIOLOGICAL_CONTEXT").fit_transform(
            records.drop(columns="annotation_provenance")
        )


def test_transform_requires_fit(records):
    with pytest.raises(NotFittedError):
        QueryPolicyTransformer().transform(records)
    with pytest.raises(NotFittedError):
        RetrievalEstimator().predict([[1, 2]])


@pytest.mark.parametrize("dataset", DATASETS)
def test_supported_manifest_families(dataset):
    manifest = replace(load_config(CONFIG)[0].dataset, dataset=dataset)
    assert DatasetManifest(**manifest.to_dict()) == manifest


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset": "unknown"},
        {"metadata_path": "../private.csv"},
        {"metadata_path": "/private/file.csv"},
        {"access": "secret"},
        {"representation_mode": "download"},
        {"retrieval_unit": "image"},
        {"metadata_sha256": "bad"},
        {"representation_path": "weights.npy"},
        {"synthetic": False},
    ],
)
def test_invalid_manifests(changes):
    with pytest.raises(ValueError):
        replace(load_config(CONFIG)[0].dataset, **changes)


def test_manifest_loading_checksums_permissions_and_records(records, tmp_path):
    manifest = load_config(CONFIG)[0].dataset
    with pytest.raises(PermissionError):
        ManifestDatasetAdapter(replace(manifest, access="restricted"), ROOT).load()
    with pytest.raises(ValueError, match="checksum"):
        ManifestDatasetAdapter(replace(manifest, metadata_sha256="0" * 64), ROOT).load()
    with pytest.raises(ValueError, match="unique"):
        validate_records(pd.concat([records, records]), manifest)
    with pytest.raises(ValueError, match="Missing record"):
        validate_records(records.drop(columns="gene"), manifest)
    with pytest.raises(ValueError, match="image_id or profile_id"):
        validate_records(records.assign(profile_id="", image_id=""), manifest)


def test_local_cpjump_adapter(tmp_path):
    path = tmp_path / "metadata.csv"
    pd.DataFrame(
        {
            "Metadata_broad_sample": ["treatment-a"],
            "Metadata_gene": ["GENE_A"],
            "Metadata_Plate": ["plate-a"],
            "Metadata_Well": ["A01"],
            "Metadata_Inferred_Batch": ["batch-a"],
        }
    ).to_csv(path, index=False)
    manifest = DatasetManifest("CPJUMP1", "tiny-v1", path.name, file_checksum(path))
    frame = CPJUMP1MetadataAdapter(manifest, tmp_path).load()
    assert frame.treatment.tolist() == ["treatment-a"]
    assert frame.gene.tolist() == ["GENE_A"]
    assert frame.split.tolist() == ["unassigned"]
    assert (
        frame.record_id.tolist()
        == CPJUMP1MetadataAdapter(manifest, tmp_path).load().record_id.tolist()
    )


@pytest.mark.parametrize(
    "kind,field",
    [
        ("held_out_plate", "plate"),
        ("held_out_treatment", "treatment"),
        ("held_out_batch", "batch"),
        ("leave_one_source_out", "source"),
        ("cross_dataset_transfer", "dataset"),
    ],
)
def test_split_contracts(records, kind, field):
    train = records.iloc[:2].copy()
    test = records.iloc[-2:].copy()
    test[field] = "heldout-value"
    SplitSpec(kind).validate(train, test)
    test[field] = train[field].iloc[0]
    # held_out_plate uses the full physical plate identity.
    if field == "plate":
        test[["dataset", "source", "batch"]] = (
            train[["dataset", "source", "batch"]].iloc[0].tolist()
        )
    with pytest.raises(ValueError, match="leakage"):
        SplitSpec(kind).validate(train, test)
    with pytest.raises(ValueError, match="nonmissing"):
        SplitSpec(kind).validate(train, test.assign(**{field: ""}))


def test_metrics_ties_missing_positives_and_counts(records):
    candidates = records.iloc[:3].copy()
    queries = records.iloc[-3:].copy().assign(query_id=["q1", "q2", "q3"])
    queries.loc[queries.index[-1], "treatment"] = "absent"
    scores = [[1, 1, 0], [0, 1, 0], [0, 0, 1]]
    result = MetricEvaluator((1, 2)).evaluate(scores, queries, candidates, SplitSpec(exclude=()))
    assert result.summary["n_evaluable_queries"] == 2
    assert result.summary["n_excluded_queries"] == 1
    assert result.summary["mAP"] == pytest.approx(0.75)
    assert result.per_query.iloc[0].average_precision == 0.5  # threshold-grouped score ties
    assert result.per_query.iloc[0].recall_at_2 == 1
    assert result.exclusions.reason.tolist() == ["no_positive_after_filtering"]


def test_filters_missing_metadata_and_treatment_exclusion(records):
    candidates = records[records.split == "test"].copy()
    queries = QueryPolicyTransformer().fit_transform(candidates)
    scores = np.ones((len(queries), len(candidates)))
    result = MetricEvaluator().evaluate(scores, queries, candidates, SplitSpec())
    assert result.summary["n_evaluable_queries"] == len(queries)
    assert {"same_plate", "same_well_coordinate", "same_record"} <= set(result.exclusions.reason)
    none = MetricEvaluator().evaluate(
        scores, queries, candidates, SplitSpec(exclude=("same_treatment",))
    )
    assert none.summary["mAP"] is None
    assert none.summary["n_evaluable_queries"] == 0
    missing = MetricEvaluator().evaluate(
        scores, queries, candidates.assign(plate=""), SplitSpec(exclude=("same_plate",))
    )
    assert missing.summary["n_evaluable_queries"] == 0


def test_treatment_aggregation_filters_before_reduction(records):
    candidates = records.iloc[:6].copy()
    queries = records.iloc[-1:].copy().assign(query_id="q1")
    result = MetricEvaluator((1,), "treatment").evaluate(
        [[0, 0, 0.9, 0, 0, 0.7]], queries, candidates, SplitSpec(exclude=())
    )
    assert result.per_query.iloc[0].n_candidates == 3
    assert result.per_query.iloc[0].n_positives == 1
    assert result.summary["mAP"] == 1


def test_bootstrap_pairs_by_id_is_reproducible_and_excludes_nan():
    a = pd.DataFrame({"query_id": ["a", "b", "c"], "average_precision": [1, 0.5, np.nan]})
    b = pd.DataFrame({"query_id": ["c", "b", "a"], "average_precision": [1, 0.25, 0.5]})
    bootstrap = QueryBootstrap(n_resamples=100, random_state=42)
    result = bootstrap.evaluate(a, b)
    assert result == bootstrap.evaluate(a.iloc[::-1], b)
    assert result["estimate"] == 0.375
    assert result["n_evaluable_queries"] == 2
    assert result["n_excluded_queries"] == 1
    with pytest.raises(ValueError, match="identical"):
        bootstrap.evaluate(a, b.iloc[:2])
    with pytest.raises(ValueError, match="unique"):
        bootstrap.evaluate(pd.concat([a, a]))


def test_pipeline_train_only_and_prediction(records):
    train, test = records[records.split == "train"], records[records.split == "test"]
    features = ["Cells_Area", "Cells_Texture"]
    y, gallery = train[features].astype(float), test[features].astype(float)
    pipeline = BenchmarkPipeline(text_embedder=TfidfTextEmbedder())
    pipeline.fit(train, y, gallery=test, gallery_y=gallery)
    assert pipeline.predict(test).shape == (len(test), len(test))
    assert pipeline.evaluate(test).summary["n_evaluable_queries"] == len(test)
    assert 0 <= pipeline.score(test) <= 1
    assert np.allclose(pipeline.morphology_embedder_.scaler_.mean_, y.mean())
    assert pipeline.text_embedder.get_params() == TfidfTextEmbedder().get_params()
    with pytest.raises(ValueError, match="leakage"):
        pipeline.predict(train)
    with pytest.raises(ValueError, match="synthetic-only"):
        BenchmarkPipeline(
            query_policy=QueryPolicyTransformer("M5_LEAKAGE_CONTROL"), synthetic=False
        ).fit(train, y, gallery=test, gallery_y=gallery)


@pytest.mark.parametrize("method", ["ridge", "pls", "cca", "unaligned_cosine"])
def test_alignment_shapes(method):
    rng = np.random.default_rng(4)
    X, y = rng.normal(size=(10, 3)), rng.normal(size=(10, 3))
    model = AlignmentEstimator(method).fit(X, y)
    assert model.predict(X[:2]).shape == (2, 3)
    if method == "unaligned_cosine":
        assert np.allclose(model.transform(X), X)
        with pytest.raises(ValueError, match="matching dimensions"):
            model.fit(X, y[:, :2])


def test_controls_and_lazy_registry(monkeypatch):
    assert len(REGISTRY) == 23
    text = ["nuclear organization", "vesicle transport"]
    assert TfidfTextEmbedder("char", (2, 3)).fit_transform(text).shape[0] == 2
    for method in ("random", "shuffled_query"):
        retriever = RetrievalEstimator(method, random_state=2).fit(np.eye(3))
        assert np.array_equal(retriever.predict(np.eye(3)), retriever.predict(np.eye(3)))
    assert RetrievalEstimator("exact_gene").fit(["TP53", "", "X"]).predict(
        ["TP53", ""]
    ).tolist() == [[1, 0, 0], [0, 0, 0]]
    monkeypatch.setattr("perturb_lm.sklearn_api.registry.find_spec", lambda name: None)
    with pytest.raises(ImportError, match="optional package"):
        require_backend(ModelConfig("biomedbert", "pinned-test-revision"))
    with pytest.raises(ValueError, match="immutable"):
        require_backend(ModelConfig("medcpt", "pending-review"))


def test_frozen_reference_is_read_only_and_queries_remain_gene_aware():
    result = frozen_check()
    assert all(
        value == "checksum_verified"
        for path, value in result["files"].items()
        if not path.startswith("outputs/")
    )
    assert IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES == [
        "Metadata_gene",
        "Metadata_pert_type",
        "Metadata_control_type",
        "Metadata_negcon_control_type",
    ]
    profiles = pd.DataFrame(
        {
            "Metadata_broad_sample": ["sample-a", "sample-b"],
            "Metadata_gene": ["GENE_A", "GENE_B"],
            "Metadata_pert_type": ["trt_cp"] * 2,
        }
    )
    queries = build_metadata_text_queries(profiles, label_column="Metadata_broad_sample")
    assert queries.mechanism_query_text.tolist() == [
        "cells with perturbation of GENE_A",
        "cells with perturbation of GENE_B",
    ]
    assert queries.query_id.tolist() == ["jump_metadata::sample-a", "jump_metadata::sample-b"]
    assert _tfidf_scores(["GENE_A"], ["GENE_A", "GENE_B"]).tolist() == [[1.0, 0.0]]


def test_plans_are_explicit_deterministic_versioned_and_write_tsv(tmp_path):
    jobs = load_config(CONFIG)
    code = {"git_commit": "abc", "dirty_worktree": True, "source_sha256": "123"}
    plan = build_plan(jobs, code, {"python": "test"})
    assert len(plan) == 4
    assert plan == build_plan(jobs, dict(reversed(list(code.items()))), {"python": "test"})
    for modified in (
        replace(jobs[0], seed=4),
        replace(jobs[0], text=ModelConfig("word_tfidf", "v2")),
        replace(jobs[0], dataset=replace(jobs[0].dataset, version="v2")),
    ):
        assert plan[0]["run_id"] != build_plan([modified], code, {"python": "test"})[0]["run_id"]
    assert (
        plan[0]["run_id"]
        != build_plan(jobs, {**code, "source_sha256": "456"}, {"python": "test"})[0]["run_id"]
    )
    write_plan(plan, tmp_path)
    assert len(pd.read_csv(tmp_path / "jobs.tsv", sep="\t")) == 4
    assert len(load_config(ROOT / "configs/benchmark_v2/expanded_staged.yaml")) == 9
    assert (
        load_config(ROOT / "configs/benchmark_v2/cpjump1_regression.yaml")[0].execution
        == "frozen_check"
    )


@pytest.mark.parametrize(
    "mutation", ["duplicate", "unknown", "cycle", "real_synthetic", "bad_resource"]
)
def test_invalid_configuration_rejected(tmp_path, mutation):
    payload = yaml.safe_load(CONFIG.read_text())
    if mutation == "duplicate":
        payload["jobs"].append(payload["jobs"][0])
    elif mutation == "unknown":
        payload["jobs"][0]["unknown_option"] = True
    elif mutation == "cycle":
        payload["jobs"][0]["depends_on"] = ["smoke_bootstrap"]
    elif mutation == "real_synthetic":
        payload["jobs"][0]["dataset"]["synthetic"] = False
    else:
        payload["jobs"][0]["resources"] = {"cpus": 0}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload))
    with pytest.raises((ValueError, TypeError)):
        load_config(path)


def test_slurm_dry_run_arrays_dependencies_resource_flags_and_shell(tmp_path):
    jobs = load_config(CONFIG)
    jobs[0] = replace(jobs[0], resources=Resources("gpu_embedding", 8, 1, 32, "01:00:00"))
    plan = build_plan(jobs, {"git_commit": "abc"})
    commands = slurm_commands(plan, tmp_path / "logs")
    assert len(commands) == 4
    assert "--gres=gpu:1" in commands[0][1]
    assert "--cpus-per-task=8" in commands[0][1]
    assert "--array=0" in commands[0][1]
    assert "--dependency=afterok:${job_0}" in commands[1][1]
    script = tmp_path / "submit.sh"
    script.write_text(
        slurm_script(plan, tmp_path / "plan.json", tmp_path / "out", tmp_path / "logs")
    )
    subprocess.run(["bash", "-n", str(script)], check=True)
    for path in (ROOT / "slurm/benchmark_v2").glob("*.sbatch"):
        subprocess.run(["bash", "-n", str(path)], check=True)
    with pytest.raises(ValueError, match="outside"):
        slurm_commands(plan, ROOT / "outputs/logs")


def test_full_synthetic_worker_resume_corruption_and_manifest(tmp_path):
    plan = build_plan(load_config(CONFIG), code_identity(ROOT))
    for job in plan:
        directory = run_job(job, tmp_path)
        assert completion_valid(directory, job["run_id"])
        stamp = (directory / "complete.json").stat().st_mtime_ns
        assert run_job(job, tmp_path) == directory
        assert (directory / "complete.json").stat().st_mtime_ns == stamp
    metric_dir = tmp_path / plan[2]["run_id"]
    metrics = json.loads((metric_dir / "metrics.json").read_text())
    assert metrics["synthetic"] is True
    assert metrics["summary"]["n_evaluable_queries"] == 6
    manifest = json.loads((metric_dir / "complete.json").read_text())
    assert {
        "models",
        "dataset_manifest",
        "split",
        "bootstrap",
        "environment",
        "output_checksums",
        "seed",
        "code",
        "query_policy",
    } <= manifest.keys()
    (metric_dir / "metrics.json").write_text("corrupt")
    assert not completion_valid(metric_dir, plan[2]["run_id"])
    run_job(plan[2], tmp_path)
    assert completion_valid(metric_dir, plan[2]["run_id"])
    tampered = copy.deepcopy(plan[0])
    tampered["configuration"]["seed"] += 1
    with pytest.raises(ValueError, match="corrupt"):
        run_job(tampered, tmp_path)
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
