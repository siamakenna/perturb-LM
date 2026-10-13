"""Bounded, approval-bound local inference; separate from benchmark dispatch."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.sklearn_api.datasets import DatasetManifest, file_checksum, present
from perturb_lm.sklearn_api.model_assets import AssetSpec, LocalModelEmbedder, asset_catalog
from perturb_lm.sklearn_api.offline_backends import ImagePreprocessing
from perturb_lm.sklearn_api.planning import (
    Resources,
    canonical_hash,
    code_identity,
    environment_info,
)
from perturb_lm.sklearn_api.queries import POLICIES, QueryPolicyTransformer
from perturb_lm.sklearn_api.workers import save_embedding_stage

ROOT = Path(__file__).resolve().parents[3]
FIELDS = {
    "schema_version",
    "name",
    "execution",
    "model",
    "dataset",
    "max_inputs",
    "batch_size",
    "resources",
    "image",
    "query_policy",
    "synthetic_spec",
}


def load_pilot(path):
    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise ValueError("Pilot manifest must be an existing file")
    payload = json.loads(manifest_path.read_text())
    if set(payload) - FIELDS or payload.get("schema_version") != 1:
        raise ValueError("Unknown pilot schema/fields")
    if payload.get("model") not in {"dinov2", "sapbert"}:
        raise ValueError("Only DINOv2 and SapBERT inference pilots are implemented")
    if payload.get("execution") not in {"plan_only", "synthetic", "approved_inference"}:
        raise ValueError("Unknown pilot execution mode")
    for name, ceiling in (("max_inputs", 8), ("batch_size", 2)):
        if type(payload.get(name)) is not int or not 1 <= payload[name] <= ceiling:
            raise ValueError(f"{name} must be in 1..{ceiling}")
    resources = Resources(**payload["resources"])
    if resources.cpus > 2 or resources.gpus or resources.memory_gb > 8:
        raise ValueError("Pilot is bounded to 2 CPUs, no GPU and 8 GiB")
    h, m, s = map(int, resources.time.split(":"))
    if h * 3600 + m * 60 + s > 600:
        raise ValueError("Pilot time is bounded to 10 minutes")
    return payload


def checked_path(root, relative, expected, tracked):
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or "://" in relative
    ):
        raise ValueError("Input paths must be explicit and relative to the supplied root")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Input missing or outside approved root")
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Pilot input exceeds 32 MiB per-file bound")
    if file_checksum(path) != expected:
        raise ValueError("Input checksum mismatch")
    tracked[path] = expected
    return path


def approval_for(payload, approval_path: Path, code, asset_root):
    if approval_path is None:
        raise PermissionError("Explicit recorded approvals are required")
    record = json.loads(approval_path.read_text())
    expected = {
        "schema_version": 1,
        "pilot_sha256": canonical_hash(payload),
        "source_commit": code["git_commit"],
        "asset_manifest_sha256": file_checksum(asset_root / "asset.json"),
    }
    if any(record.get(k) != v for k, v in expected.items()):
        raise PermissionError("Approval does not bind this pilot/source/asset manifest")
    for kind in ("asset_use", "input_use", "scientific_protocol"):
        decision = record.get("decisions", {}).get(kind, {})
        if (
            decision.get("status") != "approved"
            or decision.get("reviewer") not in {"siamakenna", "adamdiaz313-collab"}
            or not isinstance(decision.get("reference"), str)
            or not re.fullmatch(
                r"https://github.com/siamakenna/perturb-LM/(issues|pull)/[1-9][0-9]*"
                r"#(issuecomment|discussion_r|pullrequestreview)-[1-9][0-9]*",
                decision.get("reference", ""),
            )
        ):
            raise PermissionError(f"Missing recorded {kind} approval")
    if record["decisions"]["scientific_protocol"]["reviewer"] != "siamakenna":
        raise PermissionError("Scientific protocol requires the responsible owner's decision")
    return canonical_hash(record)


def run_pilot(manifest, *, data_root, asset_root, output, approval=None):
    payload = load_pilot(manifest)
    if payload["execution"] == "plan_only":
        raise PermissionError("plan_only pilot cannot execute")
    dataset = DatasetManifest(**payload["dataset"])
    synthetic = payload["execution"] == "synthetic"
    if dataset.synthetic != synthetic:
        raise PermissionError("Execution mode and dataset synthetic status differ")
    root, asset_root, output = map(Path, (data_root, asset_root, output))
    if output.exists() or output.with_name(output.name + ".working").exists():
        raise FileExistsError("Use a fresh pilot output")
    if output.resolve().is_relative_to(ROOT):
        ignored = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(output.resolve())]
        )
        if ignored.returncode:
            raise ValueError("Keep pilot outputs ignored or outside the checkout")
    code = code_identity(ROOT)

    def dirty():
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
        ).strip()

    if not synthetic and dirty():
        raise ValueError("Approved inference requires a clean reviewed source checkout")
    approval_path = None
    if not synthetic:
        if approval is None:
            raise PermissionError("Explicit recorded approvals are required")
        approval_rel = str(approval)
        if (
            not approval_rel
            or Path(approval_rel).is_absolute()
            or ".." in Path(approval_rel).parts
            or "://" in approval_rel
        ):
            raise ValueError("Approval path must be explicit and relative to the supplied data root")
        approval_path = (root / approval_rel).resolve()
        if not approval_path.is_relative_to(root.resolve()) or not approval_path.is_file():
            raise ValueError("Approval missing or outside approved root")
    approval_hash = None if synthetic else approval_for(payload, approval_path, code, asset_root)
    spec = asset_catalog()[payload["model"]]
    if synthetic:
        supplied = dict(payload.get("synthetic_spec", {}))
        for key in ("input_shape", "required_packages", "blockers"):
            if key in supplied:
                supplied[key] = tuple(supplied[key])
        spec = AssetSpec(**supplied)
        asset = json.loads((asset_root / "asset.json").read_text())
        if (
            spec.name != payload["model"]
            or not spec.identifier.startswith("synthetic/")
            or asset.get("synthetic") is not True
        ):
            raise PermissionError("Synthetic mode requires explicitly synthetic local assets")
    elif "synthetic_spec" in payload:
        raise PermissionError("Approved pretrained pilots cannot override pinned AssetSpec")
    tracked = {}
    inventory = checked_path(root, dataset.metadata_path, dataset.metadata_sha256, tracked)
    processing = None
    if spec.name == "dinov2":
        from perturb_lm.images.pixel_analyzer import read_tiff_chw

        image = payload["image"]
        if not image or image["axes"] not in {"CYX", "YXC"}:
            raise ValueError("DINOv2 requires explicit CYX or YXC TIFF axes")
        processing = ImagePreprocessing(**{k: tuple(v) for k, v in image["preprocessing"].items()})
        rows = json.loads(inventory.read_text())
        if not isinstance(rows, list) or not 1 <= len(rows) <= payload["max_inputs"]:
            raise ValueError("Image inventory exceeds bounded input count or is empty")
        ids, arrays = [], []
        for row in rows:
            if set(row) != {"record_id", "path", "sha256"}:
                raise ValueError("Image inventory permits only row identity/path/checksum")
            path = checked_path(root, row["path"], row["sha256"], tracked)
            pixels = read_tiff_chw(path, axes=image["axes"])
            processing.validate_input(pixels[None])
            if max(pixels.shape[1:]) > 1024 or pixels.shape[0] > 8:
                raise ValueError("Pilot images limited to 8 channels and 1024 by 1024")
            ids.append(row["record_id"])
            arrays.append(pixels)
        X = np.stack(arrays)  # Mixed dimensions require a separately reviewed protocol.
        if payload["query_policy"] is not None:
            raise ValueError("Image-only pilot does not accept a text query policy")
    else:
        if payload["query_policy"] != "M0_IDENTITY_FREE_V2" or payload["image"] is not None:
            raise ValueError("SapBERT pilot requires M0_IDENTITY_FREE_V2 and no image settings")
        frame = pd.read_csv(inventory, dtype=str, keep_default_na=False)
        if not 1 <= len(frame) <= payload["max_inputs"] or "record_id" not in frame:
            raise ValueError("Text inventory requires bounded rows and explicit record_id")
        rendered = QueryPolicyTransformer(payload["query_policy"]).fit_transform(frame)
        ids, X = frame.record_id.tolist(), rendered.rendered_text.tolist()
    if any(not isinstance(i, str) or not present(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Pilot requires unique nonempty string row identities")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    encoder = LocalModelEmbedder(
        spec, asset_root, batch_size=payload["batch_size"], image_preprocessing=processing
    ).fit(X)
    embeddings = encoder.transform(X)
    # Frozen adapter fit is validation, never alignment/training or learned preprocessing.
    if embeddings.dtype != np.float32 or not np.allclose(
        np.linalg.norm(embeddings, axis=1), 1, atol=1e-5
    ):
        raise ValueError("Pilot expected finite float32 unit-normalized embeddings")
    if any(file_checksum(path) != digest for path, digest in tracked.items()):
        raise ValueError("Input changed during inference")
    if code_identity(ROOT) != code or (not synthetic and dirty()):
        raise ValueError("Source changed during inference")
    from perturb_lm.sklearn_api.model_assets import validate_asset

    if validate_asset(asset_root, spec) != encoder.asset_manifest_:
        raise ValueError("Asset changed during inference")
    provenance = {
        "scope": "synthetic_inference" if synthetic else "approved_pretrained_inference_only",
        "code": code,
        "pilot_sha256": canonical_hash(payload),
        "approval_sha256": approval_hash,
        "input_inventory_sha256": dataset.metadata_sha256,
        "asset_manifest_sha256": file_checksum(asset_root / "asset.json"),
        "model": asdict(spec),
        "image_processing": payload["image"],
        "query_policy": None
        if spec.name == "dinov2"
        else {
            "name": payload["query_policy"],
            "version": POLICIES[payload["query_policy"]].version,
        },
        "row_ids_sha256": canonical_hash(ids),
        "source_unchanged": True,
        "environment": environment_info(),
        "alignment": "none",
        "model_packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "tokenizers", "safetensors")
        },
    }
    provenance["run_id"] = canonical_hash(provenance)
    return save_embedding_stage(embeddings, ids, output, provenance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Show proposed contract; never load assets")
    inspect.add_argument("--manifest", type=Path, required=True)
    run = commands.add_parser("run", help="One bounded local inference; no scheduling")
    run.add_argument("--manifest", type=Path, required=True)
    for name in ("data-root", "asset-root", "out"):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--approval", type=Path)
    args = parser.parse_args()
    if args.command == "inspect":
        payload = load_pilot(args.manifest)
        print(
            json.dumps(
                {
                    "execution": payload["execution"],
                    "pilot_sha256": canonical_hash(payload),
                    "proposed_asset": asdict(asset_catalog()[payload["model"]]),
                    "approval_verified": False,
                    "assets_verified": False,
                    "inputs_verified": False,
                },
                indent=2,
            )
        )
    else:
        run_pilot(
            args.manifest,
            data_root=args.data_root,
            asset_root=args.asset_root,
            output=args.out,
            approval=args.approval,
        )
        print("Inference complete; outputs remain local and are not benchmark results")


if __name__ == "__main__":
    main()
