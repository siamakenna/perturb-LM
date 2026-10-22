"""Verify preserved Phase 5 inputs using hashes and metadata only (#30,#52)."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from perturb_lm.audits.cohort import (
    BATCH,
    KIND,
    checksum,
    clean,
    count_values,
    join_cohort,
    read_table,
    replication,
    source_tables,
)


class VerificationError(ValueError):
    def __init__(self, evidence):
        super().__init__("Preserved metadata verification failed; census stopped")
        self.evidence = evidence


def manifest_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Manifest path must be relative and confined to its input root")
    # Normalize before filesystem access, check a directory-boundary prefix, and
    # return the checked canonical path rather than the original symlink spelling.
    # This is also the validation idiom documented by CodeQL for path injection.
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root_real, relative))
    if not candidate.startswith(root_real.rstrip(os.sep) + os.sep):
        raise ValueError("Manifest input missing or outside its input root")
    path = Path(candidate)
    if not path.is_file():
        raise ValueError("Manifest input missing or outside its input root")
    return path


def metadata_profiles(root, manifest):
    """Read original header and metadata only; hash the compressed file bytes separately."""
    frames, checks = [], []
    for number, entry in enumerate(manifest):
        path = manifest_path(root, entry["relative_path"])
        actual_hash = checksum(path)
        with gzip.open(path, "rt", newline="") as stream:
            reader = csv.DictReader(stream)
            header = reader.fieldnames
            if len(header) != len(set(header)):
                raise ValueError("Duplicate source profile columns")
            fields = [c for c in header if c.startswith("Metadata_")]
            features = [
                c for c in header if c.startswith(("Cells_", "Cytoplasm_", "Nuclei_", "Image_"))
            ]
            records = [{c: clean(row[c]) for c in fields} for row in reader]
        table = pd.DataFrame(records, columns=fields)
        table["audit_file"] = entry["relative_path"]
        table["audit_row"] = list(range(len(table)))
        table["record_id"] = [f"file{number:03d}:row{i:06d}" for i in range(len(table))]
        table["path_batch"] = BATCH
        frames.append(table)
        checks.append(
            {
                "file_index": number,
                "sha256": actual_hash,
                "hash_matches": actual_hash == entry["sha256"],
                "row_count_matches": len(table) == entry["rows"],
                "observed_plate_set_matches": sorted(set(table.Metadata_Plate) - {""})
                == entry["plates_observed_in_rows"],
                "feature_count_matches": len(features) == entry["feature_count"],
                "feature_schema_matches": hashlib.sha256("\n".join(features).encode()).hexdigest()
                == entry["feature_schema_sha256"],
            }
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(), checks


def compare_mapping(preserved, reconstructed):
    """Require complete row identities and every original column; never fill missing rows."""
    counts = {}
    for name, frame in (("preserved", preserved), ("reconstructed", reconstructed)):
        counts[name + "_duplicate_record_ids"] = int(frame.record_id.duplicated(keep=False).sum())
    if any(counts.values()):
        return counts | {"matches": False}
    a, b = preserved.set_index("record_id"), reconstructed.set_index("record_id")
    counts["missing_original_rows"] = len(set(b.index) - set(a.index))
    counts["extra_original_rows"] = len(set(a.index) - set(b.index))
    counts["missing_original_columns"] = len(set(b.columns) - set(a.columns))
    common = a.index.intersection(b.index).sort_values()
    mismatches = {
        c: int(a.loc[common, c].map(clean).ne(b.loc[common, c].map(clean)).sum())
        for c in a.columns.intersection(b.columns)
    }
    counts["field_disagreement_rows"] = {k: v for k, v in sorted(mismatches.items()) if v}
    counts["matches"] = not (
        any(v for k, v in counts.items() if k != "field_disagreement_rows")
        or counts["field_disagreement_rows"]
    )
    return counts


def verify_inputs(audit_root, data_root):
    logical = {
        "original_mapping": audit_root / "cohort/local_mapping_PRIVATE.csv",
        "original_profile_manifest": audit_root / "cohort/profile_manifest.json",
        "original_cohort_summary": audit_root / "cohort/cohort_summary.json",
        "original_source_provenance": audit_root / "source/provenance.json",
    }
    hashes = {k: checksum(v) for k, v in logical.items()}
    mapping = read_table(logical["original_mapping"])
    manifests = json.loads(logical["original_profile_manifest"].read_text())
    original = json.loads(logical["original_cohort_summary"].read_text())
    provenance = json.loads(logical["original_source_provenance"].read_text())
    source_root = audit_root / "source"
    evidence = {"input_manifest_sha256": hashes, "source_revision": provenance["revision"]}
    source_checks = []
    for i, entry in enumerate(provenance["files"]):
        path = manifest_path(source_root, Path(entry["path"]).name)
        actual = checksum(path)
        source_checks.append(
            {
                "file_index": i,
                "sha256": actual,
                "hash_matches": actual == entry["sha256"],
                "cohort_summary_hash_matches": actual == original["source_files"].get(path.name),
                "byte_count_matches": path.stat().st_size == entry["bytes"],
            }
        )
    profiles, profile_checks = metadata_profiles(data_root, manifests)
    actual_files = {
        p.relative_to(data_root).as_posix()
        for p in (data_root / "profiles" / BATCH).rglob(f"*{KIND}.csv.gz")
    }
    manifest_files = [m["relative_path"] for m in manifests]
    evidence.update(
        source_files=source_checks,
        source_file_set_matches=(
            {Path(e["path"]).name for e in provenance["files"]} == set(original["source_files"])
            and len({Path(e["path"]).name for e in provenance["files"]}) == len(source_checks)
        ),
        profile_files=profile_checks,
        profile_file_set_matches=set(manifest_files) == actual_files,
        duplicate_profile_manifest_entries=len(manifest_files) - len(set(manifest_files)),
        expected_manifest_sizes_match=len(profile_checks) == 12 and len(source_checks) == 11,
        source_revision_matches_cohort_summary=provenance["revision"]
        == original["source_revision"],
        scope=(
            "All compressed profile bytes hashed; headers and metadata read, no "
            "numeric feature values parsed; all original source files hashed; "
            "complete mapping rejoined in memory"
        ),
        provenance_limit=(
            "Original mapping has no previously frozen own-file digest; current "
            "digest binds this audit. Agreement with all original raw rows/source "
            "joins supplies independent completeness checks, not a retroactive "
            "signature."
        ),
    )
    evidence["hash_and_manifest_verification_passed"] = (
        evidence["expected_manifest_sizes_match"]
        and evidence["source_file_set_matches"]
        and evidence["profile_file_set_matches"]
        and not evidence["duplicate_profile_manifest_entries"]
        and evidence["source_revision_matches_cohort_summary"]
        and all(
            all(v for k, v in c.items() if k.endswith("matches"))
            for c in source_checks + profile_checks
        )
    )
    if not evidence["hash_and_manifest_verification_passed"]:
        raise VerificationError(evidence)
    tables = source_tables(source_root)
    selected_source = tables[0][tables[0].Batch.eq(BATCH)]
    evidence["source_inventory_reproduction"] = {
        "experiment_records_all_collections": len(tables[0]),
        "selected_batch_plates": len(selected_source),
        "selected_batch_modalities": count_values(selected_source.Perturbation),
        "matches_historical_source_counts": (
            len(selected_source) == original.get("source_plate_count")
            and count_values(selected_source.Perturbation) == original.get("source_modalities")
        ),
    }
    reconstructed = join_cohort(profiles, *tables)
    comparison = compare_mapping(mapping, reconstructed)
    evidence["complete_original_mapping_reproduction"] = comparison
    # Counts are recomputed on the full input, never used to reconstruct or select records.
    rep, _ = replication(reconstructed)
    actual = {
        "local_files": len(profile_checks),
        "local_rows": len(reconstructed),
        "labeled_rows": int(reconstructed.broad_sample.ne("").sum()),
        "missing_treatment_rows": int(reconstructed.broad_sample.eq("").sum()),
        "local_plate_count": reconstructed.Assay_Plate_Barcode.nunique(),
        "resolved_rows": int(reconstructed.resolved.sum()),
        "unresolved_rows": int((~reconstructed.resolved).sum()),
        "annotation_conflict_rows": int(reconstructed.annotation_conflict.sum()),
        "local_modalities": count_values(reconstructed.Perturbation),
        "local_cell_types": count_values(reconstructed.Cell_type),
        "replication": rep,
    }
    evidence["historical_count_reproduction"] = {
        k: {"observed": v, "matches": v == original[k]} for k, v in actual.items()
    }
    evidence["verified"] = (
        comparison["matches"]
        and evidence["source_inventory_reproduction"]["matches_historical_source_counts"]
        and all(x["matches"] for x in evidence["historical_count_reproduction"].values())
    )
    # Recheck immutable inputs after reading; the CLI repeats this after its census as well.
    evidence["input_manifests_unchanged_during_verification"] = all(
        checksum(v) == hashes[k] for k, v in logical.items()
    )
    evidence["verified"] &= evidence["input_manifests_unchanged_during_verification"]
    if not evidence["verified"]:
        raise VerificationError(evidence)
    return mapping, tables[-1], evidence, logical
