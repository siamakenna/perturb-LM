"""Strict explicit jobs, canonical identities, and public-safe runtime provenance."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from perturb_lm.sklearn_api.contracts import RelevanceContract
from perturb_lm.sklearn_api.datasets import DatasetManifest, file_checksum
from perturb_lm.sklearn_api.queries import POLICIES
from perturb_lm.sklearn_api.registry import ModelConfig
from perturb_lm.sklearn_api.splits import SplitSpec

STAGES = ("embedding", "alignment", "retrieval", "bootstrap")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Resources:
    resource_class: str = "cpu_smoke"
    cpus: int = 2
    gpus: int = 0
    memory_gb: int = 4
    time: str = "00:10:00"

    def __post_init__(self):
        if self.resource_class not in {
            "cpu_smoke",
            "cpu_standard",
            "gpu_embedding",
            "gpu_training",
        }:
            raise ValueError("Unknown resource class")
        if (
            any(type(v) is not int for v in (self.cpus, self.gpus, self.memory_gb))
            or self.cpus < 1
            or self.gpus < 0
            or self.memory_gb < 1
        ):
            raise ValueError("Invalid CPU/GPU/memory request")
        if not re.fullmatch(r"\d{2,3}:[0-5]\d:[0-5]\d", self.time) or self.time == "00:00:00":
            raise ValueError("Time must be a positive HH:MM:SS duration")


@dataclass(frozen=True)
class BootstrapConfig:
    n_resamples: int = 1000
    confidence: float = 0.95
    seed: int = 0

    def __post_init__(self):
        if type(self.n_resamples) is not int or self.n_resamples < 1 or not 0 < self.confidence < 1:
            raise ValueError("Invalid bootstrap settings")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("Bootstrap seed must be a nonnegative integer")


@dataclass(frozen=True)
class JobConfig:
    name: str
    stage: str
    scientific_stage: str
    dataset: DatasetManifest
    text: ModelConfig
    morphology: ModelConfig
    alignment: ModelConfig
    query_policy: str
    split: SplitSpec
    relevance_contract: str | None = None
    seed: int = 0
    top_k: tuple[int, ...] = (1, 5, 10)
    depends_on: tuple[str, ...] = ()
    resources: Resources = field(default_factory=Resources)
    bootstrap: BootstrapConfig = field(default_factory=BootstrapConfig)
    execution: str = "plan_only"
    controlled_variable: str = "none"
    fixed_variables: tuple[str, ...] = ()
    production_readiness: str = "blocked"
    blockers: tuple[str, ...] = ()
    experimental_opt_in: bool = False

    def __post_init__(self):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise ValueError("Job names must be lowercase safe identifiers")
        if self.stage not in STAGES or self.query_policy not in POLICIES:
            raise ValueError("Unknown execution stage or query policy")
        if self.relevance_contract is None:
            object.__setattr__(self, "relevance_contract", self.query_policy)
        contracts = load_relevance_contracts()
        if self.relevance_contract not in contracts:
            raise ValueError(f"Unknown relevance contract: {self.relevance_contract}")
        if self.scientific_stage not in {
            "synthetic_contract",
            "frozen_regression",
            "expanded_pilot",
            "transfer",
        }:
            raise ValueError("Unknown scientific stage")
        if self.execution not in {"synthetic", "frozen_check", "plan_only"}:
            raise ValueError("Real benchmark execution is not enabled in Phase 1")
        if self.controlled_variable not in {
            "none",
            "text_encoder",
            "morphology_representation",
            "alignment",
            "split",
            "dataset",
        }:
            raise ValueError("Unknown controlled variable")
        if self.production_readiness not in {
            "synthetic_only",
            "schema_tested",
            "blocked",
            "ready_pending_cluster",
        }:
            raise ValueError("Unknown production readiness status")
        if type(self.experimental_opt_in) is not bool:
            raise ValueError("experimental_opt_in must be boolean")
        if (
            self.text.spec.family not in {"text", "control"}
            or self.morphology.spec.family != "morphology"
            or self.alignment.spec.family != "alignment"
        ):
            raise ValueError("Model is registered in the wrong modality")
        if (
            type(self.seed) is not int
            or self.seed < 0
            or not self.top_k
            or any(type(k) is not int or k < 1 for k in self.top_k)
        ):
            raise ValueError("Require nonnegative seed and positive integer top_k")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Duplicate job dependencies")
        if self.execution == "synthetic":
            contract = contracts[self.relevance_contract]
            contract.require_execution(self.dataset.synthetic)
            if contract.retrieval_unit != self.dataset.retrieval_unit:
                raise ValueError("Dataset retrieval unit differs from relevance contract")
            if tuple(self.split.exclude) != contract.exclusions:
                raise ValueError("Split exclusions differ from relevance contract")
            if contract.query_unit != "record":
                raise ValueError("Synthetic worker supports record queries only")
            if not self.dataset.synthetic or self.scientific_stage != "synthetic_contract":
                raise ValueError(
                    "Synthetic execution requires an explicitly synthetic dataset/stage"
                )
            if (self.text.name, self.morphology.name, self.alignment.name) != (
                "word_tfidf",
                "cellprofiler",
                "ridge",
            ):
                raise ValueError(
                    "The Phase 1 synthetic worker supports word_tfidf/cellprofiler/ridge only"
                )
        if self.execution == "frozen_check" and (
            self.stage != "retrieval"
            or self.scientific_stage != "frozen_regression"
            or self.query_policy != "M0_GENE_AWARE_V1"
            or self.dataset.dataset != "CPJUMP1"
            or self.split.kind != "unfiltered"
            or self.split.exclude
        ):
            raise ValueError("Frozen checks must reference the gene-aware frozen regression")
        if self.execution != "plan_only":
            if any(
                m.revision == "pending-review" for m in (self.text, self.morphology, self.alignment)
            ):
                raise ValueError("Execution requires pinned model revisions")
            if POLICIES[self.query_policy].provisional and not self.dataset.synthetic:
                raise ValueError("Provisional policies are synthetic-only")
        if POLICIES[self.query_policy].provisional and not self.experimental_opt_in:
            raise ValueError("Provisional policies require explicit experimental_opt_in")


def load_config(path: Path | str) -> list[JobConfig]:
    payload = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "jobs"}
        or payload["schema_version"] != 1
    ):
        raise ValueError("Config requires schema_version: 1 and explicit jobs")
    if not isinstance(payload["jobs"], list) or not payload["jobs"]:
        raise ValueError("Config requires at least one explicit job")
    jobs = [parse_job(raw) for raw in payload["jobs"]]
    validate_jobs(jobs)
    return jobs


def parse_job(raw: dict) -> JobConfig:
    raw = dict(raw)
    raw.setdefault("relevance_contract", raw.get("query_policy"))
    raw.setdefault(
        "controlled_variable",
        {
            "embedding": "text_encoder",
            "alignment": "alignment",
            "retrieval": "none",
            "bootstrap": "none",
        }[raw["stage"]],
    )
    raw.setdefault(
        "production_readiness",
        "synthetic_only" if raw.get("execution") == "synthetic" else "blocked",
    )
    raw.setdefault(
        "blockers",
        tuple() if raw.get("execution") == "synthetic" else ("needs_scientific_approval",),
    )
    raw.setdefault("experimental_opt_in", False)
    raw["dataset"] = DatasetManifest(**raw["dataset"])
    for key in ("text", "morphology", "alignment"):
        raw[key] = ModelConfig(**raw[key])
    split = dict(raw["split"])
    if "exclude" in split:
        split["exclude"] = tuple(split["exclude"])
    if "group_fields" in split:
        split["group_fields"] = tuple(split["group_fields"])
    raw["split"] = SplitSpec(**split)
    raw["resources"] = Resources(**raw.get("resources", {}))
    raw["bootstrap"] = BootstrapConfig(**raw.get("bootstrap", {}))
    for key in ("depends_on", "top_k"):
        if key in raw:
            raw[key] = tuple(raw[key])
    for key in ("fixed_variables", "blockers"):
        if key in raw:
            raw[key] = tuple(raw[key])
    return JobConfig(**raw)


def validate_jobs(jobs: list[JobConfig]) -> None:
    previous = {}
    for job in jobs:
        if job.name in previous:
            raise ValueError("Duplicate job name")
        for dependency in job.depends_on:
            if dependency not in previous or STAGES.index(
                previous[dependency].stage
            ) >= STAGES.index(job.stage):
                raise ValueError(
                    "Dependencies must reference earlier jobs in earlier execution stages"
                )
            parent = previous[dependency]
            if job.execution != "plan_only" and parent.execution != job.execution:
                raise ValueError("Executable jobs cannot depend on planning-only jobs")
            for key in ("dataset", "query_policy", "relevance_contract", "split", "seed"):
                if getattr(job, key) != getattr(parent, key):
                    raise ValueError(f"Dependency changes the scientific contract: {key}")
            if job.stage != "bootstrap":
                for key in ("text", "morphology", "alignment"):
                    if getattr(job, key) != getattr(parent, key):
                        raise ValueError(f"Dependency changes representation: {key}")
        if job.execution == "synthetic":
            expected_stage = {
                "alignment": "embedding",
                "retrieval": "alignment",
                "bootstrap": "retrieval",
            }.get(job.stage)
            counts = {"embedding": {0}, "alignment": {1}, "retrieval": {1}, "bootstrap": {1, 2}}
            if len(job.depends_on) not in counts[job.stage] or any(
                previous[name].stage != expected_stage for name in job.depends_on
            ):
                raise ValueError("Synthetic jobs require an embedding/alignment/retrieval chain")
        previous[job.name] = job


def code_identity(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    commit = git("rev-parse", "HEAD")
    # Include new uncommitted implementation files; exclude generated/user artifacts.
    relevant = [
        root / "src/perturb_lm/sklearn_api",
        root / "src/perturb_lm/retrieval/text_profile.py",
        root / "src/perturb_lm/modeling/phase3c.py",
        root / "configs/benchmark_v2",
        root / "slurm/benchmark_v2",
        root / "tests/fixtures/benchmark_v2",
    ]
    paths = sorted(
        p
        for entry in relevant
        for p in (entry.rglob("*") if entry.is_dir() else [entry])
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    paths += [root / "pyproject.toml"]
    return {
        "git_commit": commit,
        "source_sha256": canonical_hash(
            {str(p.relative_to(root)): file_checksum(p) for p in paths}
        ),
    }


def load_relevance_contracts() -> dict[str, RelevanceContract]:
    path = Path(__file__).resolve().parents[3] / "configs/benchmark_v2/relevance_contracts.yaml"
    payload = yaml.safe_load(path.read_text())
    return {
        name: RelevanceContract.from_dict(values) for name, values in payload["contracts"].items()
    }


def environment_info() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scipy", "scikit-learn", "PyYAML")
        },
    }


def build_plan(jobs: list[JobConfig], code: dict, environment: dict | None = None) -> list[dict]:
    validate_jobs(jobs)
    environment = environment if environment is not None else environment_info()
    plan, ids = [], {}
    for job in jobs:
        config = asdict(job)
        policy = POLICIES[job.query_policy]
        identity = {
            "configuration": config,
            "code": {k: v for k, v in code.items() if k != "dirty_worktree"},
            "environment": environment,
            "relevance": load_relevance_contracts()[job.relevance_contract].to_dict(),
            "query_policy_version": policy.version,
            "dependencies": [ids[name] for name in job.depends_on],
        }
        run_id = canonical_hash(identity)
        ids[job.name] = run_id
        plan.append(
            {
                "row": len(plan),
                "run_id": run_id,
                "configuration_hash": canonical_hash(config),
                **identity,
                "model_identifiers": {
                    k: getattr(job, k).spec.identifier for k in ("text", "morphology", "alignment")
                },
            }
        )
    return plan


def write_plan(plan: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    with (out / "jobs.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row",
                "run_id",
                "name",
                "stage",
                "scientific_stage",
                "controlled_variable",
                "production_readiness",
                "experimental_opt_in",
                "resource_class",
                "execution",
                "depends_on",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for job in plan:
            cfg = job["configuration"]
            writer.writerow(
                {
                    "row": job["row"],
                    "run_id": job["run_id"],
                    **{k: cfg[k] for k in ("name", "stage", "scientific_stage", "execution")},
                    "controlled_variable": cfg["controlled_variable"],
                    "production_readiness": cfg["production_readiness"],
                    "experimental_opt_in": cfg["experimental_opt_in"],
                    "resource_class": cfg["resources"]["resource_class"],
                    "depends_on": ",".join(job["dependencies"]),
                }
            )


def run_manifest(job: dict, outputs: list[Path]) -> dict:
    return {
        "schema_version": 1,
        "run_id": job["run_id"],
        "code": job["code"],
        "configuration_hash": job["configuration_hash"],
        "configuration": job["configuration"],
        "dependencies": job["dependencies"],
        "dataset_manifest": job["configuration"]["dataset"],
        "models": {
            k: {**job["configuration"][k], "identifier": job["model_identifiers"][k]}
            for k in ("text", "morphology", "alignment")
        },
        "query_policy": {
            "name": job["configuration"]["query_policy"],
            "version": job["query_policy_version"],
        },
        "relevance_contract": job["relevance"],
        "split": job["configuration"]["split"],
        "seed": job["configuration"]["seed"],
        "bootstrap": job["configuration"]["bootstrap"],
        "environment": environment_info(),
        "output_checksums": {p.name: file_checksum(p) for p in outputs},
    }
