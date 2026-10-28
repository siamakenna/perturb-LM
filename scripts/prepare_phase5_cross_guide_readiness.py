#!/usr/bin/env python3
"""Offline HGNC preparation from a verified census receipt; never reads profiles (#30,#52)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from plan_phase5_1_rotations import guarded_output

from perturb_lm.audits.cohort import checksum, read_table
from perturb_lm.audits.gene_identity import resolution_summary, resolve_symbols
from perturb_lm.audits.guide_support import attach_identities
from perturb_lm.audits.json_inputs import read_json_snapshot, read_tsv_snapshot
from perturb_lm.audits.rotations import _validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--census-summary", type=Path, required=True)
    parser.add_argument("--expected-summary-sha256", required=True)
    parser.add_argument("--hgnc-approved", type=Path, required=True)
    parser.add_argument("--hgnc-withdrawn", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--census-root", type=Path, default=Path.cwd(),
        help="Census JSON directory beneath invocation directory (default: invocation directory)",
    )
    parser.add_argument(
        "--reference-root", type=Path, default=Path.cwd(),
        help="Reference JSON/HGNC TSV root within invocation directory (default: same directory)",
    )
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    out = guarded_output(args.out, root)
    if out.exists():
        raise ValueError("Use a fresh ignored output directory")
    census_snapshot = read_json_snapshot(args.census_summary, root=args.census_root)
    if census_snapshot.sha256 != args.expected_summary_sha256:
        raise ValueError("Census receipt checksum mismatch")
    census = census_snapshot.value
    if (
        census["status"] not in {"COMPLETE", "COMPLETED_DESCRIPTIVE_METADATA_AUDIT"}
        or not census["verification"]["verified"]
    ):
        raise ValueError("A complete verified metadata census receipt is required")
    reference_snapshot = read_json_snapshot(args.reference_manifest, root=args.reference_root)
    reference = reference_snapshot.value
    approved = read_tsv_snapshot(args.hgnc_approved, root=args.reference_root)
    withdrawn = read_tsv_snapshot(args.hgnc_withdrawn, root=args.reference_root)
    for name, snapshot in (("approved", approved), ("withdrawn", withdrawn)):
        if snapshot.sha256 != reference[name]["sha256"]:
            raise ValueError("Pinned HGNC reference checksum mismatch")
    mapping_path = args.audit_root / "cohort/local_mapping_PRIVATE.csv"
    provenance_path = args.audit_root / "source/provenance.json"
    for key, path in (
        ("original_mapping", mapping_path),
        ("original_source_provenance", provenance_path),
    ):
        if checksum(path) != census["verification"]["input_manifest_sha256"][key]:
            raise ValueError("Original metadata input differs from verified census receipt")
    provenance = json.loads(provenance_path.read_text())
    annotation = next(
        f
        for f in provenance["files"]
        if Path(f["path"]).name == "JUMP-Target-1_crispr_metadata.tsv"
    )
    annotation_path = args.audit_root / "source" / Path(annotation["path"]).name
    if checksum(annotation_path) != annotation["sha256"]:
        raise ValueError("Original source annotation checksum mismatch")
    mapping = read_table(mapping_path)
    annotations = read_table(annotation_path)
    annotations["Perturbation"] = "crispr"
    identities, conflicts = attach_identities(mapping, annotations)
    selected = _validate(identities)
    usable = selected[selected.broad_sample.ne("") & ~selected.is_control]
    records = resolve_symbols(
        set(usable.source_gene), approved.rows, withdrawn.rows
    )
    aggregate = resolution_summary(records)
    unchanged = (
        aggregate["nomenclature_assigned_source_strings"] == aggregate["source_gene_strings"]
        and not aggregate["stable_IDs_merging_multiple_source_strings"]
    )
    summary = {
        "status": "COMPLETE_NOMENCLATURE_PREPARATION_NOT_BIOLOGICAL_REVIEW",
        "protocol_status": "PROPOSED_NOT_APPROVED",
        "census_receipt_sha256": args.expected_summary_sha256,
        "original_mapping_sha256": checksum(mapping_path),
        "source_provenance_sha256": checksum(provenance_path),
        "annotation_sha256": checksum(annotation_path),
        "reference_manifest_sha256": reference_snapshot.sha256,
        "HGNC_references": reference,
        "resolution": aggregate,
        "identity_conflict_counts": conflicts,
        "source_gene_to_assigned_HGNC_partition_is_one_to_one_complete": unchanged,
        "eligibility_interpretation": (
            "Nomenclature mapping preserves all source-string group partitions; original metadata "
            "eligibility counts are unchanged by nomenclature alone. Guide review remains pending."
            if unchanged
            else "Original counts remain source-string capacity; changed/unknown group partitions "
            "require a separately reviewed identity-aware capacity assessment before execution."
        ),
        "source_gene_strings_split_automatically": 0,
        "code_git_sha": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "code_changes_present": bool(
            subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain"], text=True
            ).strip()
        ),
        "implementation_sha256": {
            name: checksum(root / name)
            for name in (
                "scripts/prepare_phase5_cross_guide_readiness.py",
                "src/perturb_lm/audits/gene_identity.py",
                "src/perturb_lm/audits/json_inputs.py",
                "src/perturb_lm/audits/guide_support.py",
                "src/perturb_lm/audits/rotations.py",
            )
        },
        "profiles_read": False,
        "census_rerun": False,
        "scores_computed": False,
        "scientific_execution_authorized": False,
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("identity-ledger_PRIVATE.json", records),
        ("identity-summary.json", summary),
    ):
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (out / "SHA256SUMS").write_text(
        "".join(
            f"{checksum(out / name)}  {name}\n"
            for name in ("identity-ledger_PRIVATE.json", "identity-summary.json")
        )
    )
    print(json.dumps(aggregate, sort_keys=True))


if __name__ == "__main__":
    main()
