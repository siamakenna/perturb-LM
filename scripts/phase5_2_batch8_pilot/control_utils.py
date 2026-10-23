#!/usr/bin/env python3
"""Look up two plates in pinned public metadata; no profile or numeric reads."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REVISION = "016e865fa0691244e0860943e41c7d6a88ed2580"
REPOSITORY = "jump-cellpainting/datasets"
LAYOUT_SHA = "fff903fd3f9f61e45cb8b9c5506df06dc366fa7980f6cb7990077cf22e938d9f"
QC_SHA = "34e55c0ad86d03ac31d681af03c81f55347a9dc0baac6d891e6c8fb3c54f5a98"
PLATES = {"BR00123523": "Target1", "BR00121428": "Target2"}
FILE_LIMITS = {"metadata/well.csv.gz": 10 * 1024 * 1024,
               "metadata/perturbation_control.csv": 64 * 1024}
HEADERS = ["Metadata_Source", "Metadata_Plate", "Metadata_Well", "Metadata_JCP2022"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def canonical_well(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([A-Pa-p])(0?[1-9]|1[0-9]|2[0-4])", value.strip())
    return f"{match[1].upper()}{int(match[2]):02d}" if match else None


def validate_blob(path, api_obj, relative_path, max_bytes):
    size, blob_sha = api_obj.get("size"), api_obj.get("sha")
    if (api_obj.get("type") != "file" or api_obj.get("path") != relative_path
            or type(size) is not int or not 0 < size <= max_bytes
            or not isinstance(blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_sha)):
        raise ValueError("Unexpected GitHub file metadata or size")
    path = Path(path)
    if path.stat().st_size != size:
        raise ValueError("Downloaded file length differs from the GitHub receipt")
    digest = hashlib.sha1(f"blob {size}\0".encode())
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != blob_sha:
        raise ValueError("Downloaded bytes do not match the pinned Git blob")
    return {"path": relative_path, "bytes": size, "git_blob_sha1": blob_sha,
            "sha256": sha256(path), "revision": REVISION}


def fetch_file(relative_path, max_bytes, out):
    if relative_path not in FILE_LIMITS or max_bytes > FILE_LIMITS[relative_path]:
        raise ValueError("Only the two bounded public metadata files are allowed")
    out = Path(out)
    response = subprocess.run([
        "gh", "api", "--hostname", "github.com", "--method", "GET",
        "-H", "Accept: application/vnd.github.object+json",
        f"repos/{REPOSITORY}/contents/{relative_path}?ref={REVISION}"],
        check=False, capture_output=True, timeout=90)
    if response.returncode:
        detail = response.stderr.decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"GitHub metadata request failed: {detail}")
    if len(response.stdout) > 16 * 1024 * 1024:
        raise ValueError("GitHub metadata response exceeds the bound")
    api_obj = json.loads(response.stdout)
    write_json(out / (Path(relative_path).name + ".api.json"), api_obj)
    size = api_obj.get("size")
    if (api_obj.get("type") != "file" or api_obj.get("path") != relative_path
            or type(size) is not int or not 0 < size <= max_bytes):
        raise ValueError("Unexpected file receipt; download not attempted")
    partial = out / (Path(relative_path).name + ".partial")
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{relative_path}"
    subprocess.run(["curl", "--disable", "--fail", "--show-error", "--silent",
                    "--proto", "=https", "--connect-timeout", "15", "--max-time", "90",
                    "--max-filesize", str(size), "--output", str(partial), url], check=True)
    receipt = validate_blob(partial, api_obj, relative_path, max_bytes)
    partial.rename(out / Path(relative_path).name)
    receipt["url"] = url
    return receipt


def read_control_registry(text):
    reader = csv.DictReader(io.StringIO(text))
    expected = ["Metadata_JCP2022", "Metadata_pert_type", "Metadata_Name", "Metadata_modality"]
    if reader.fieldnames != expected:
        raise ValueError("Unexpected control registry columns")
    registry = {}
    for row in reader:
        key = row["Metadata_JCP2022"]
        if None in row or any(value is None for value in row.values()) or not re.fullmatch(r"JCP2022_[0-9]{6}", key):
            raise ValueError("Malformed control registry row")
        if key in registry:
            raise ValueError("Duplicate control registry identifier")
        registry[key] = row
    for key, required in (("JCP2022_033924", ("negcon", "DMSO", "compound")),
                          ("JCP2022_999999", ("empty", "Empty", "any"))):
        row = registry.get(key, {})
        if tuple(row.get(name) for name in expected[1:]) != required:
            raise ValueError("Required DMSO or empty sentinel has changed")
    return registry


def classify_control(jcp_id, registry):
    if jcp_id is None or jcp_id == "":
        return "missing_identifier"
    if not isinstance(jcp_id, str) or not re.fullmatch(r"JCP2022_[0-9]{6}", jcp_id):
        return "invalid_identifier"
    if jcp_id not in registry:
        return "not_listed_in_control_registry"
    row = registry[jcp_id]
    if jcp_id == "JCP2022_033924":
        return "registered_dmso_negative_control"
    if row["Metadata_pert_type"] == "empty":
        return "registered_empty"
    if row["Metadata_modality"] not in ("compound", "any"):
        return "registered_other_modality_control"
    return {"poscon": "registered_positive_control", "negcon": "registered_other_negative_control"}.get(
        row["Metadata_pert_type"], "registered_unrecognized_control_type")


def load_reviewed_inputs(layout_path, qc_path):
    if sha256(layout_path) != LAYOUT_SHA or sha256(qc_path) != QC_SHA:
        raise ValueError("Local layout or QC bytes differ from the reviewed inputs")
    by_layout = {name: {} for name in PLATES.values()}
    with Path(layout_path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            by_layout[row["layout"]][row["well_position"]] = row
    qc = json.loads(Path(qc_path).read_text())
    observed = {}
    for record in qc["plates"]:
        plate = record["plate"]
        missing = {row["well_position"] for row in record["missing_well_public_layout_records"]}
        expected_missing = set() if plate == "BR00123523" else {"H14"}
        if plate not in PLATES or missing != expected_missing:
            raise ValueError("Unexpected prior missing-well evidence")
        observed[plate] = set(by_layout[PLATES[plate]]) - missing
        if len(observed[plate]) != record["validity_counts"]["rows"]:
            raise ValueError("Prior profile coverage does not reconcile")
    return {plate: by_layout[name] for plate, name in PLATES.items()}, observed


def read_selected_wells(gzip_path):
    selected = {plate: {} for plate in PLATES}
    with gzip.open(gzip_path, "rb") as handle:
        def bounded_lines():
            used = 0
            while True:
                raw = handle.readline(1024 * 1024 + 1)
                if not raw:
                    break
                used += len(raw)
                if len(raw) > 1024 * 1024 or used > 256 * 1024 * 1024:
                    raise ValueError("Decompressed well metadata exceeds the bound")
                yield raw.decode("utf-8")
        reader = csv.reader(bounded_lines())
        header = next(reader)
        if len(header) != len(set(header)) or any(name not in header for name in HEADERS):
            raise ValueError("Unexpected well metadata columns")
        indices = [header.index(name) for name in HEADERS]
        for number, row in enumerate(reader, 1):
            if number > 2000000 or len(row) != len(header):
                raise ValueError("Well metadata row bound or shape violation")
            source, plate, raw_well, jcp_id = (row[index] for index in indices)
            if source != "source_4" or plate not in selected:
                continue
            well = canonical_well(raw_well)
            if well is None or well in selected[plate]:
                raise ValueError("Invalid or duplicate selected source/plate/well annotation")
            selected[plate][well] = jcp_id
    return selected


def layout_class(row):
    if row["included_in_key_comparison"] == "True":
        return "included_treatment"
    if row["control_type"].startswith("poscon"):
        return "positive_labelled_control"
    if "missing_map_sample_identifier" in row["exclusion_reasons"]:
        return "missing_map_identifier"
    return "other_excluded"


def summarize_plate(plate, layout_rows, well_annotations, observed_wells, registry):
    full, observed, missing_map, catalog = Counter(), Counter(), Counter(), Counter()
    for well, row in layout_rows.items():
        design = layout_class(row)
        label = (classify_control(well_annotations[well], registry) if well in well_annotations
                 else "missing_well_annotation")
        full[(design, label)] += 1
        catalog[label] += 1
        if well in observed_wells:
            observed[(design, label)] += 1
        if design == "missing_map_identifier":
            missing_map[label] += 1
    to_rows = lambda counts: [{"layout_class": d, "catalog_class": c, "wells": n}
                              for (d, c), n in sorted(counts.items())]
    dmso = "registered_dmso_negative_control"
    conflicts = {
        "included_treatment_positions_with_registered_control_or_empty": sum(
            n for (d, c), n in full.items() if d == "included_treatment" and c.startswith("registered_")),
        "positive_labelled_control_positions_with_dmso_or_empty": sum(
            n for (d, c), n in full.items() if d == "positive_labelled_control"
            and c in (dmso, "registered_empty")),
        "positions_with_other_modality_control": catalog["registered_other_modality_control"],
    }
    return {"plate": plate, "layout_wells": len(layout_rows),
            "public_well_annotations": len(well_annotations), "observed_profile_wells_from_prior_qc": len(observed_wells),
            "layout_wells_without_annotation": len(set(layout_rows) - set(well_annotations)),
            "annotations_outside_layout": len(set(well_annotations) - set(layout_rows)),
            "observed_profile_wells_without_annotation": len(observed_wells - set(well_annotations)),
            "catalog_classification_counts": dict(catalog),
            "source_labeled_dmso_wells": catalog[dmso],
            "observed_source_labeled_dmso_wells": sum(n for (d, c), n in observed.items() if c == dmso),
            "label_differences_requiring_review": conflicts,
            "requires_label_adjudication": any(conflicts.values()),
            "full_layout_cross_tab": to_rows(full), "observed_profile_cross_tab": to_rows(observed),
            "missing_map_identifier_positions": {"total": sum(missing_map.values()),
                "catalog_classification_counts": dict(missing_map), "dmso": missing_map[dmso],
                "registered_non_dmso": sum(n for c, n in missing_map.items() if c.startswith("registered_") and c != dmso),
                "missing_annotation": missing_map["missing_well_annotation"]}}


def run(layout_path, qc_path, out):
    out = Path(out)
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        layouts, observed = load_reviewed_inputs(layout_path, qc_path)
        receipts = [fetch_file(name, bound, out) for name, bound in FILE_LIMITS.items()]
        registry = read_control_registry((out / "perturbation_control.csv").read_text())
        annotations = read_selected_wells(out / "well.csv.gz")
        report = {"status": "PUBLIC_CONTROL_ANNOTATION_REVIEW_NOT_COHORT_APPROVAL",
                  "created_utc": datetime.now(timezone.utc).isoformat(), "repository": REPOSITORY,
                  "revision": REVISION, "implementation_sha256": sha256(__file__),
                  "layout_sha256": LAYOUT_SHA, "prior_qc_sha256": QC_SHA, "source_files": receipts,
                  "profile_availability_evidence": "reviewed_prior_qc_report; profiles_not_reread",
                  "plates": [summarize_plate(p, layouts[p], annotations[p], observed[p], registry) for p in PLATES],
                  "profile_downloads_or_numeric_reads": False, "normalization_or_scoring_performed": False,
                  "contracts_changed": False,
                  "limitations": ["Unlisted identifiers are not automatically classified as treatments.",
                                  "Public annotation does not independently validate reagent delivery, culture independence or phenotype.",
                                  "DMSO labels alone do not approve normalization, cohort selection or an experiment.",
                                  "Image-prefixed fields were not read or classified as exclusively technical features."]}
        write_json(out / "batch8-control-annotations.json", report)
        files = sorted(path for path in out.iterdir() if path.is_file())
        (out / "SHA256SUMS").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files))
        return report
    except Exception as exc:
        write_json(out / "control-lookup-error.json", {"status": "INCOMPLETE", "exception": type(exc).__name__,
                                                      "message": str(exc), "partial_files_preserved": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout-wells", type=Path, required=True)
    parser.add_argument("--qc-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.layout_wells, args.qc_report, args.out)
    print(f"PASS: return only {args.out / 'batch8-control-annotations.json'}")


if __name__ == "__main__":
    main()
