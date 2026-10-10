#!/usr/bin/env python3
"""Prepare (never submit) one DINOv2 run using the repository's existing worker.

The request file contains private paths, not approvals. The existing native
worker remains responsible for enforcing its full approval and asset contracts.
No download, model loading, or inference occurs in this program.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from comparator_tools import (
    confined_file,
    digest,
    fresh_output_path,
    new_output,
    read_json,
    validate_native_record_ids,
    write_json,
)

REQUEST_KEYS = {"manifest", "approval", "data_root", "asset_root", "pilot_output"}


def make_request(path: Path) -> None:
    path = fresh_output_path(path)
    if not sys.stdin.isatty():
        raise ValueError("Use an interactive terminal; do not pipe commands into these prompts")
    print("Enter existing reviewed paths. No approvals will be created.")
    print("Leave any field empty to abort without saving. Do not paste more commands at a prompt.")
    data = {}
    for key in sorted(REQUEST_KEYS):
        raw = input(f"{key}: ").strip()
        if not raw:
            raise ValueError("Unresolved path; request was not saved")
        p = Path(raw).expanduser()
        if not p.is_absolute():
            raise ValueError("Enter an absolute local path")
        if key == "pilot_output":
            p = fresh_pilot_output(p)
        elif key in {"manifest", "approval"}:
            if not p.is_file():
                raise ValueError("An input file is missing")
        elif not p.is_dir():
            raise ValueError("An input directory is missing")
        data[key] = str(p)
    write_json(path, data)
    print("Saved a PRIVATE path request. No inspection, approval, or job submission performed.")


def fresh_pilot_output(path: Path) -> Path:
    try:
        path = fresh_output_path(path)
        fresh_output_path(path.with_name(path.name + ".working"))
    except OSError as exc:
        raise ValueError("Choose a fresh output whose parent exists, including .working") from exc
    return path


def validate_request(
    request: Path, code: Path, sha: str
) -> tuple[dict, dict, list[tuple[Path, str]]]:
    raw = read_json(request)
    if not isinstance(raw, dict) or set(raw) != REQUEST_KEYS:
        raise ValueError(
            "Request must contain manifest, approval, data_root, asset_root, pilot_output"
        )
    paths = {}
    for key, value in raw.items():
        if (
            not isinstance(value, str)
            or not value.strip()
            or not Path(value).expanduser().is_absolute()
        ):
            raise ValueError(f"UNRESOLVED: {key}")
        path = Path(value).expanduser()
        # Resolving the leaf would hide an existing dangling output symlink.
        path = fresh_pilot_output(path) if key == "pilot_output" else path.resolve()
        if path.is_relative_to(code):
            raise ValueError(
                "Private manifests, data, assets, and outputs "
                "must remain outside the source checkout"
            )
        paths[key] = path
    for key in ("data_root", "asset_root"):
        if not paths[key].is_dir():
            raise ValueError(f"Missing {key}")
    for key in ("manifest", "approval"):
        if not paths[key].is_file():
            raise ValueError(f"Missing {key}")
    if not paths["approval"].is_relative_to(paths["data_root"]):
        raise ValueError("Approval must resolve inside the supplied data root")
    manifest = read_json(paths["manifest"])
    approval = read_json(paths["approval"])
    if not isinstance(manifest, dict) or not isinstance(approval, dict):
        raise ValueError("Manifest and approval must be JSON objects")
    if manifest.get("model") != "dinov2" or manifest.get("execution") != "approved_inference":
        raise ValueError(
            "This launcher accepts a reviewed DINOv2 approved_inference manifest only; "
            "it will not edit plan_only"
        )
    expected_resources = {"cpus": 2, "gpus": 0, "memory_gb": 8, "time": "00:10:00"}
    resources = manifest.get("resources", {})
    if not isinstance(resources, dict) or any(
        resources.get(k) != v for k, v in expected_resources.items()
    ):
        raise ValueError(
            "Manifest resources must match the reviewed first-pilot CPU wrapper: "
            "2 CPUs, no GPU, 8 GiB, 10 minutes"
        )
    limit = manifest.get("max_inputs")
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("First DINOv2 pilot must be bounded to at most eight inputs")
    if approval.get("source_commit") != sha:
        raise ValueError("Approval source_commit does not match the selected source")
    dataset = manifest.get("dataset", {})
    if not isinstance(dataset, dict):
        raise ValueError("Manifest dataset must be a JSON object")
    if dataset.get("synthetic") is not False or dataset.get("version") in {
        None,
        "",
        "pending-approval",
    }:
        raise ValueError("Real reviewed dataset version is unresolved")
    inventory = confined_inventory(paths["data_root"], dataset.get("metadata_path"))
    expected_hash = dataset.get("metadata_sha256")
    if not isinstance(expected_hash, str) or digest(inventory) != expected_hash:
        raise ValueError("Inventory checksum differs from the manifest")
    rows = read_json(inventory)
    if not isinstance(rows, list) or not 1 <= len(rows) <= limit:
        raise ValueError("Input inventory exceeds bounds or is empty")
    if any(
        not isinstance(row, dict) or set(row) != {"record_id", "path", "sha256"} for row in rows
    ):
        raise ValueError("Unexpected image inventory fields")
    validate_native_record_ids([r["record_id"] for r in rows])
    bindings = [
        (request.resolve(), digest(request)),
        (paths["manifest"], digest(paths["manifest"])),
        (paths["approval"], digest(paths["approval"])),
        (inventory, digest(inventory)),
    ]
    for row in rows:
        image = confined_file(paths["data_root"], row["path"])
        if image.stat().st_size > 32 * 1024 * 1024 or digest(image) != row["sha256"]:
            raise ValueError("Image size or checksum does not satisfy the inventory")
        bindings.append((image, row["sha256"]))
    asset_manifest = paths["asset_root"] / "asset.json"
    if not asset_manifest.is_file():
        raise ValueError("Missing native asset.json")
    bindings.append((asset_manifest, digest(asset_manifest)))
    return paths, {"manifest": manifest, "n_images": len(rows)}, bindings


def confined_inventory(root: Path, value: object) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        raise ValueError("metadata_path must be a relative inventory path without parent traversal")
    path = (root / value).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Input inventory escaped the selected data root")
    return path


def prepare(request: Path, code: Path, python: Path, sha: str, out: Path) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("Expected a full source commit SHA")
    code = code.resolve(strict=True)
    # Do not resolve the executable symlink: preserve its virtual-environment identity.
    python = Path(os.path.abspath(python.expanduser()))
    if python.name != "python" or python.parent.name != "bin" or not os.access(python, os.X_OK):
        raise ValueError("Select the existing environment's bin/python")
    out = fresh_output_path(out)
    if out.is_relative_to(code):
        raise ValueError("Use a fresh preparation directory outside the source checkout")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(code), *args], text=True).strip()

    if git("rev-parse", "HEAD") != sha or git("status", "--porcelain"):
        raise ValueError("Expected a clean checkout at the selected reviewed source")
    worker = code / "src/perturb_lm/sklearn_api/pilot.py"
    wrapper = code / "slurm/phase4_pilot.sbatch"
    if not worker.is_file() or not wrapper.is_file():
        raise ValueError("Existing native worker or Slurm wrapper is missing")
    paths, details, bindings = validate_request(request, code, sha)
    if out.resolve() == paths["pilot_output"]:
        raise ValueError("Preparation directory must differ from the pilot output directory")
    bindings += [(worker, digest(worker)), (wrapper, digest(wrapper))]
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.update(
        PYTHONPATH=str(code / "src"),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
    )
    out = new_output(out)
    with (
        (out / "environment.stdout.private.txt").open("xb") as so,
        (out / "environment.stderr.private.txt").open("xb") as se,
    ):
        subprocess.run(
            [
                str(python),
                "-c",
                "import pathlib,sys,importlib.metadata as m; "
                "import perturb_lm.sklearn_api.pilot as p; "
                "assert pathlib.Path(p.__file__).resolve()==pathlib.Path(sys.argv[1]).resolve(); "
                "print(sys.version); "
                "print({k:m.version(k) for k in ('torch','transformers','numpy','tifffile')})",
                str(worker),
            ],
            cwd=code,
            env=env,
            check=True,
            timeout=60,
            stdout=so,
            stderr=se,
        )
    with (
        (out / "inspect.stdout.private.txt").open("xb") as so,
        (out / "inspect.stderr.private.txt").open("xb") as se,
    ):
        subprocess.run(
            [
                str(python),
                "-m",
                "perturb_lm.sklearn_api.pilot",
                "inspect",
                "--manifest",
                str(paths["manifest"]),
            ],
            cwd=code,
            env=env,
            check=True,
            timeout=120,
            stdout=so,
            stderr=se,
        )
    if (
        git("rev-parse", "HEAD") != sha
        or git("status", "--porcelain")
        or any(digest(p) != h for p, h in bindings)
    ):
        raise ValueError("Source or bound input changed during inspection")
    bindings_path = out / "bindings.private.json"
    write_json(bindings_path, {str(p): h for p, h in bindings})
    variables = {
        "PILOT_CODE": str(code),
        "PILOT_ENV": str(python.parent.parent),
        "PILOT_MANIFEST": str(paths["manifest"]),
        "PILOT_APPROVAL": str(paths["approval"].relative_to(paths["data_root"])),
        "PILOT_DATA": str(paths["data_root"]),
        "PILOT_ASSETS": str(paths["asset_root"]),
        "PILOT_OUT": str(paths["pilot_output"]),
        "PILOT_EXPECTED_SHA": sha,
        "PILOT_BINDINGS": str(bindings_path.resolve()),
        "PILOT_BINDINGS_SHA256": digest(bindings_path),
    }
    with (out / "launch.env.sh").open("x") as f:
        for key, value in variables.items():
            f.write(f"export {key}={shlex.quote(value)}\n")
    report = {
        "scope": "native_inspection_and_launch_preparation_not_submission",
        "source_commit": sha,
        "model": "dinov2",
        "n_images": details["n_images"],
        "device_requested": "cpu",
        "cpus": 2,
        "memory_gb": 8,
        "walltime": "00:10:00",
        "manifest_file_sha256": digest(paths["manifest"]),
        "asset_manifest_sha256": digest(paths["asset_root"] / "asset.json"),
        "input_inventory_sha256": details["manifest"]["dataset"]["metadata_sha256"],
        "native_inspection_exit_code": 0,
        "pretrained_inference_performed": False,
        "native_full_approval_and_asset_validation": (
            "enforced_by_native_worker_at_run_time_not_reimplemented"
        ),
        "operator_must_verify_linked_decisions": True,
        "submission_authorized_by_this_program": False,
    }
    write_json(out / "preparation-summary.json", report)
    return report


def main() -> None:
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser(
        "make-request", help="Interactively record existing private paths; no approval creation"
    )
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser(
        "prepare", help="Validate basic bounds and invoke native inspect; never submit"
    )
    for name in ("request", "code", "python", "out"):
        s.add_argument(f"--{name}", type=Path, required=True)
    s.add_argument("--source-sha", required=True)
    a = p.parse_args()
    try:
        if a.command == "make-request":
            make_request(a.out)
        else:
            print(json.dumps(prepare(a.request, a.code, a.python, a.source_sha, a.out), indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"STOP: {type(exc).__name__}: {exc}") from exc


if __name__ == "__main__":
    main()
