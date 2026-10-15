#!/usr/bin/env python3
"""Audit four local Target compound TSVs; no downloads, scores or experiment approval."""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from perturb_lm.audits.layouts import compare_compound_layouts, read_tsv, sha256, write_json

ROLES = ("target1_metadata", "target1_platemap", "target2_metadata", "target2_platemap")
SOURCE_FILENAMES = {
    "target1_metadata": "JUMP-Target-1_compound_metadata.tsv",
    "target1_platemap": "JUMP-Target-1_compound_platemap.tsv",
    "target2_metadata": "JUMP-Target-2_compound_metadata.tsv",
    "target2_platemap": "JUMP-Target-2_compound_platemap.tsv",
}
OUTPUT_NAMES = (
    "summary.json",
    "standardized-key-groups_PRIVATE.json",
    "layout-wells_PRIVATE.csv",
    "annotation-ledger_PRIVATE.json",
    "SHA256SUMS",
)


def guarded_output(out: Path, repository: Path) -> Path:
    """Allow a fresh directory only in this source tree's ignored outputs directory."""
    repository = repository.resolve(strict=True)
    output_root = repository / "outputs"
    if output_root.is_symlink() or output_root.resolve() != output_root:
        raise ValueError("The outputs root must not redirect through a symlink")
    result = out.resolve()
    if result == output_root or not result.is_relative_to(output_root) or result.exists():
        raise ValueError("Choose a fresh directory underneath this source tree's outputs/")
    # The supplied source archive need not be a Git checkout. Enforce its root ignore rule.
    rules = (repository / ".gitignore").read_text().splitlines()
    if "/outputs/" not in rules or any(rule.startswith("!") for rule in rules):
        raise ValueError("Expected an unconditional /outputs/ Git ignore rule")
    if (repository / ".git").exists():
        for name in OUTPUT_NAMES:
            ignored = subprocess.run(
                ["git", "-C", str(repository), "check-ignore", "--quiet", str(result / name)],
                capture_output=True,
                check=False,
            )
            if ignored.returncode != 0:
                raise ValueError("All output files must be Git-ignored")
    return result


def resolve_inputs(args: argparse.Namespace, repository: Path) -> tuple[dict, dict]:
    import json

    if args.synthetic_fixture:
        if args.provenance:
            raise ValueError("Synthetic mode does not accept an external provenance manifest")
        root = repository / "tests/fixtures/phase5_2"
        paths = {role: root / f"{role}.tsv" for role in ROLES}
        provenance = {"evidence_kind": "synthetic_fixture", "upstream_revision": None}
    else:
        if args.provenance is None:
            raise ValueError("Real metadata requires --provenance")
        root = args.metadata_dir.resolve(strict=True)
        manifest = json.loads(args.provenance.read_text())
        revision = manifest.get("revision", "")
        if (
            manifest.get("schema_version") != 1
            or manifest.get("repository") != "jump-cellpainting/JUMP-Target"
            or not isinstance(revision, str)
            or not re.fullmatch(r"[a-f0-9]{40}", revision)
            or set(manifest.get("files", {})) != set(ROLES)
        ):
            raise ValueError("Invalid source provenance schema, repository, revision or file roles")
        prefix = f"https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/{revision}/"
        paths, source_files = {}, {}
        for role in ROLES:
            item = manifest["files"][role]
            relative = PurePosixPath(item.get("path", ""))
            url, expected = item.get("url", ""), item.get("sha256", "")
            if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
                raise ValueError("Source file paths must stay within --metadata-dir")
            path = (root / str(relative)).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("Source file paths must stay within --metadata-dir")
            if (
                url != prefix + SOURCE_FILENAMES[role]
                or not isinstance(expected, str)
                or not re.fullmatch(r"[a-f0-9]{64}", expected)
                or sha256(path) != expected
            ):
                raise ValueError("Source URL/revision or SHA256 verification failed")
            paths[role] = path
            source_files[role] = {"url": url, "sha256": expected}
        if len(set(paths.values())) != 4:
            raise ValueError("The four source roles must refer to four distinct files")
        provenance = {
            "evidence_kind": "operator_supplied_public_metadata",
            "source_repository": manifest["repository"],
            "upstream_revision": revision,
            "source_provenance_manifest_sha256": sha256(args.provenance),
            "source_files": source_files,
            "source_binding": "local_checksums_verified_upstream_origin_not_contacted",
        }
    return paths, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--metadata-dir", type=Path)
    group.add_argument("--synthetic-fixture", action="store_true")
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    repository = Path(__file__).resolve().parents[1]
    out = guarded_output(args.out, repository)
    paths, provenance = resolve_inputs(args, repository)
    before = {role: sha256(path) for role, path in paths.items()}
    tables = [read_tsv(paths[role]) for role in ROLES]
    summary, keys, wells, annotations = compare_compound_layouts(*tables)
    if before != {role: sha256(path) for role, path in paths.items()}:
        raise ValueError("Input files changed during the audit")
    summary.update(provenance)
    summary["input_sha256"] = before
    summary["implementation_sha256"] = {
        "script": sha256(Path(__file__)),
        "module": sha256(repository / "src/perturb_lm/audits/layouts.py"),
    }
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(out / "summary.json", summary)
    write_json(out / "standardized-key-groups_PRIVATE.json", keys)
    write_json(out / "annotation-ledger_PRIVATE.json", annotations)
    with (out / "layout-wells_PRIVATE.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(wells[0]))
        writer.writeheader()
        writer.writerows(wells)
    (out / "SHA256SUMS").write_text(
        "".join(f"{sha256(out / name)}  {name}\n" for name in OUTPUT_NAMES[:-1])
    )
    print("PROPOSED_NOT_APPROVED: compound layout design crosswalk complete.")
    print(f"Shared standardized key groups: {summary['shared_standardized_key_groups']}")
    print("No measured replication, biological relevance, scoring, or execution was established.")
    print(f"Local outputs: {out}")


if __name__ == "__main__":
    main()
