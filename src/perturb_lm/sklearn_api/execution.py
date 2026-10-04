"""Local synthetic worker and dry-run SLURM construction; no remote execution."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.sklearn_api.datasets import DatasetManifest, ManifestDatasetAdapter, file_checksum
from perturb_lm.sklearn_api.estimators import (
    AlignmentEstimator,
    MorphologyEmbedder,
    RetrievalEstimator,
    TfidfTextEmbedder,
)
from perturb_lm.sklearn_api.evaluation import MetricEvaluator, QueryBootstrap
from perturb_lm.sklearn_api.planning import (
    STAGES,
    build_plan,
    canonical_hash,
    code_identity,
    environment_info,
    load_config,
    parse_job,
    run_manifest,
    write_plan,
)
from perturb_lm.sklearn_api.queries import QueryPolicyTransformer
from perturb_lm.sklearn_api.splits import SplitSpec

ROOT = Path(__file__).resolve().parents[3]


def frozen_check(root: Path = ROOT) -> dict:
    fixture = json.loads((root / "tests/fixtures/benchmark_v2/frozen_reference.json").read_text())
    report = {"kind": "frozen_artifact_verification_only", "files": {}}
    for section in ("tracked_contract", "local_result_artifacts"):
        for relative, expected in fixture[section].items():
            path = root / relative
            if not path.exists() and section == "local_result_artifacts":
                report["files"][relative] = "unavailable"
                continue
            if not path.is_file() or file_checksum(path) != expected:
                raise ValueError(f"Frozen reference changed: {relative}")
            report["files"][relative] = "checksum_verified"
    return report


def completion_valid(directory: Path, run_id: str) -> bool:
    path = directory / "complete.json"
    if not path.exists():
        return False
    try:
        manifest = json.loads(path.read_text())
        checksums = manifest["output_checksums"]
        return (
            manifest["run_id"] == run_id
            and bool(checksums)
            and all(
                Path(name).name == name
                and (directory / name).is_file()
                and file_checksum(directory / name) == digest
                for name, digest in checksums.items()
            )
        )
    except (ValueError, KeyError, OSError):
        return False


def _json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _frame_json(frame: pd.DataFrame) -> list:
    return json.loads(frame.to_json(orient="records"))


def run_job(job: dict, output_root: Path, data_root: Path = ROOT) -> Path:
    cfg = job["configuration"]
    validated = parse_job(cfg)
    if job["model_identifiers"] != {
        key: getattr(validated, key).spec.identifier for key in ("text", "morphology", "alignment")
    }:
        raise ValueError("Plan model identifiers differ from the registry")
    identity = {
        key: job[key]
        for key in ("configuration", "code", "environment", "query_policy_version", "dependencies")
    }
    if (
        canonical_hash(identity) != job["run_id"]
        or canonical_hash(cfg) != job["configuration_hash"]
    ):
        raise ValueError("Plan identity is corrupt; regenerate the plan")
    if cfg["execution"] == "plan_only":
        raise RuntimeError(
            "This is a planning-only job; implement/review its Phase 2 backend before execution"
        )
    current = code_identity(ROOT)
    if (
        any(current[k] != job["code"][k] for k in ("git_commit", "source_sha256"))
        or environment_info() != job["environment"]
    ):
        raise ValueError("Code/environment changed since planning; regenerate the plan")
    directory = output_root / job["run_id"]
    if completion_valid(directory, job["run_id"]):
        return directory
    dependencies = [output_root / run_id for run_id in job["dependencies"]]
    for path, run_id in zip(dependencies, job["dependencies"], strict=True):
        if not completion_valid(path, run_id):
            raise ValueError(f"Dependency is incomplete or corrupt: {run_id}")
    directory.mkdir(parents=True, exist_ok=True)
    # Exclusive lock prevents concurrent array retries from writing the same run.
    lock = directory / ".running"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError(
            "Run is locked; verify no worker is active before removing .running"
        ) from error
    os.close(descriptor)
    working = output_root / f".{job['run_id']}.working-{os.getpid()}"
    try:
        if working.exists():
            raise RuntimeError("A working directory with this process identity already exists")
        working.mkdir(parents=True)
        (directory / "complete.json").unlink(missing_ok=True)
        if cfg["execution"] == "frozen_check":
            _json(working / "verification.json", frozen_check())
            temporary_outputs = [working / "verification.json"]
        else:
            temporary_outputs = _synthetic_stage(cfg, dependencies, working, data_root)
        outputs = []
        for temporary in temporary_outputs:
            final = directory / temporary.name
            temporary.replace(final)
            outputs.append(final)
        manifest = run_manifest(job, outputs)
        # The executing dirty flag may differ due to unrelated user files; record both.
        manifest["execution_code"] = current
        _json(directory / "complete.tmp", manifest)
        (directory / "complete.tmp").replace(directory / "complete.json")
    finally:
        lock.unlink(missing_ok=True)
        shutil.rmtree(working, ignore_errors=True)
    return directory


def _synthetic_stage(cfg, dependencies, directory, data_root):
    stage = cfg["stage"]
    if stage == "embedding":
        frame = ManifestDatasetAdapter(DatasetManifest(**cfg["dataset"]), data_root).load()
        train, test = frame[frame.split == "train"], frame[frame.split == "test"]
        split = SplitSpec(**cfg["split"])
        split.validate(train, test)
        policy = QueryPolicyTransformer(cfg["query_policy"]).fit(frame)
        train_queries, test_queries = policy.transform(train), policy.transform(test)
        embedder = TfidfTextEmbedder().fit(train_queries.rendered_text.tolist())
        features = [f for f in frame if f.startswith("Cells_")]
        if not features:
            raise ValueError("Synthetic fixture requires explicit Cells_ morphology features")
        morph = MorphologyEmbedder().fit(train[features].astype(float))
        arrays = {
            "train_text": embedder.transform(train_queries.rendered_text).toarray(),
            "test_text": embedder.transform(test_queries.rendered_text).toarray(),
            "train_morphology": morph.transform(train[features].astype(float)),
            "test_morphology": morph.transform(test[features].astype(float)),
        }
        context = {
            "queries": _frame_json(test_queries),
            "gallery": _frame_json(test),
            "synthetic": True,
        }
    elif stage in {"alignment", "retrieval"}:
        if len(dependencies) != 1:
            raise ValueError(f"Synthetic {stage} requires one previous-stage dependency")
        with np.load(dependencies[0] / "arrays.npz", allow_pickle=False) as saved:
            arrays = dict(saved)
        context = json.loads((dependencies[0] / "context.json").read_text())
        if stage == "alignment":
            projection = AlignmentEstimator().fit(arrays["train_text"], arrays["train_morphology"])
            arrays["projected"] = projection.transform(arrays["test_text"])
        else:
            scores = (
                RetrievalEstimator().fit(arrays["test_morphology"]).predict(arrays["projected"])
            )
            result = MetricEvaluator(
                tuple(cfg["top_k"]), cfg["dataset"]["retrieval_unit"]
            ).evaluate(
                scores,
                pd.DataFrame(context["queries"]),
                pd.DataFrame(context["gallery"]),
                SplitSpec(**cfg["split"]),
            )
            _json(
                directory / "metrics.json",
                {
                    "synthetic": True,
                    "summary": result.summary,
                    "per_query": _frame_json(result.per_query),
                    "exclusions": _frame_json(result.exclusions),
                },
            )
            return [directory / "metrics.json"]
    elif stage == "bootstrap":
        if len(dependencies) not in {1, 2}:
            raise ValueError(
                "Bootstrap requires a retrieval dependency and optional paired reference"
            )
        frames = [
            pd.DataFrame(json.loads((path / "metrics.json").read_text())["per_query"])
            for path in dependencies
        ]
        settings = cfg["bootstrap"]
        result = QueryBootstrap(
            settings["n_resamples"], settings["confidence"], settings["seed"]
        ).evaluate(frames[0], frames[1] if len(frames) == 2 else None)
        _json(directory / "bootstrap.json", {"synthetic": True, **result})
        return [directory / "bootstrap.json"]
    else:
        raise ValueError(f"Unknown stage: {stage}")
    np.savez_compressed(directory / "arrays.npz", **arrays)
    _json(directory / "context.json", context)
    return [directory / "arrays.npz", directory / "context.json"]


def slurm_commands(plan: list[dict], log_root: Path) -> list[tuple[str, list[str]]]:
    """Group only equal stage/resource/dependency jobs into arrays; never submit."""
    if not log_root.is_absolute() or log_root.resolve().is_relative_to(ROOT):
        raise ValueError("SLURM logs require an absolute path outside the repository")
    commands, groups, names = [], {}, {}
    for stage in STAGES:
        for job in plan:
            cfg = job["configuration"]
            if cfg["stage"] != stage:
                continue
            if cfg["execution"] == "plan_only":
                continue
            dependency_vars = tuple(sorted({names[d] for d in job["dependencies"]}))
            key = (stage, canonical_hash(cfg["resources"]), dependency_vars)
            if key not in groups:
                groups[key] = []
            groups[key].append(job)
            names[job["run_id"]] = f"job_{list(groups).index(key)}"
    for index, ((stage, _, deps), jobs) in enumerate(groups.items()):
        resource = jobs[0]["configuration"]["resources"]
        args = [
            "sbatch",
            "--parsable",
            f"--array={','.join(str(j['row']) for j in jobs)}",
            f"--cpus-per-task={resource['cpus']}",
            f"--mem={resource['memory_gb']}G",
            f"--time={resource['time']}",
            f"--output={log_root}/%x-%A_%a.out",
            f"--error={log_root}/%x-%A_%a.err",
            f"--job-name=plm_v2_{stage}",
        ]
        if resource["gpus"]:
            args += [f"--gres=gpu:{resource['gpus']}", "--partition=gpu"]
        if deps:
            args += ["--dependency=afterok:" + ":".join("${" + dep + "}" for dep in deps)]
        args += [str(ROOT / "slurm/benchmark_v2" / f"{stage}.sbatch")]
        commands.append((f"job_{index}", args))
    return commands


def slurm_script(plan, plan_path, output_root, log_root) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"export BENCHMARK_PLAN={shlex.quote(str(plan_path.resolve()))}",
        f"export BENCHMARK_OUTPUT={shlex.quote(str(output_root.resolve()))}",
        f"export BENCHMARK_REPO={shlex.quote(str(ROOT))}",
        f"mkdir -p {shlex.quote(str(log_root))}",
    ]
    for name, args in slurm_commands(plan, log_root):
        rendered = " ".join(
            '"' + arg + '"' if arg.startswith("--dependency=") else shlex.quote(arg) for arg in args
        )
        lines += [f"{name}=$({rendered})", f'{name}="${{{name}%%;*}}"']
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    planner = sub.add_parser("plan")
    planner.add_argument("config", type=Path)
    planner.add_argument("--out", type=Path, required=True)
    planner.add_argument("--log-root", type=Path)
    worker = sub.add_parser("run")
    worker.add_argument("--plan", type=Path, required=True)
    worker.add_argument("--row", type=int, required=True)
    worker.add_argument("--stage", choices=STAGES)
    worker.add_argument("--out", type=Path, required=True)
    worker.add_argument("--data-root", type=Path, default=ROOT)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "outputs"):
        parser.error("Generated files inside the repository must be under ignored outputs/")
    if args.command == "plan":
        plan = build_plan(load_config(args.config), code_identity(ROOT))
        write_plan(plan, args.out)
        if args.log_root:
            (args.out / "submit.sh").write_text(
                slurm_script(plan, args.out / "plan.json", args.out / "runs", args.log_root)
            )
        print(f"Planned {len(plan)} explicit jobs; no jobs submitted")
    else:
        plan = json.loads(args.plan.read_text())
        if not 0 <= args.row < len(plan):
            parser.error("Row index outside the plan")
        job = plan[args.row]
        if args.stage and job["configuration"]["stage"] != args.stage:
            parser.error("Array row does not match template stage")
        print(run_job(job, args.out, args.data_root))


if __name__ == "__main__":
    main()
