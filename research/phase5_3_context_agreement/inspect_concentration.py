#!/usr/bin/env python3
"""Post hoc aggregate diagnostics for the exact completed Phase 5.3 result.

Reads only its aggregate summary, hash manifest and per-source-gene CSV.
Does not read profiles, re-score, curate identities or change the original run.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import statistics
import subprocess
import sys
import uuid

EXPECTED_SOURCE = "589ad24f14eec0ac8b726f37ba89abef1a5316b2"
EXPECTED_SUMMARY_SHA256 = "1d325458adfffd4488869a6e5c2b19da65ecbf9adb3aa1bc8028b3b1f72ed79e"
MASKS = ("different_row_and_column", "different_coordinate")
CSV_NAME = "PRIVATE/crossguide_private_genes.csv"
MAX_SUMMARY_BYTES = 256 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 4096
COLUMNS = [
    "mask", "gene", "source_gene_status", "initial_anchor_wells",
    "initial_sequence_guides", "initial_plates", "finite_anchor_wells",
    "label_usable_anchor_wells", "no_metadata_positive_anchor_gallery_comparisons",
    "no_metadata_reference_anchor_gallery_comparisons", "complete_guide_pairs",
    "contrast", "position_contrast", "complete_pair_eligible", "weight",
]
COUNT_COLUMNS = COLUMNS[3:11]
STATUS_NAMES = {
    "usable_recorded_source_gene_string_only",
    "unknown_or_missing_source_gene",
    "unresolved_well_like_source_gene_identifier_ambiguity",
    "unresolved_multitoken_source_gene_string",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded_bytes(path, limit):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Required input must be a regular non-symlink file")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Input exceeds its byte bound")
    return value


def check_ancestors(path, boundary):
    """Allow OS aliases above the physical checkout, never internal symlinks."""
    if ".." in path.parts:
        raise ValueError("Parent traversal is not allowed")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Internal symlink input or output is not allowed")
        if part.resolve() == boundary:
            return
    raise ValueError("Path is outside the checkout")


def git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], check=False,
                          text=True, capture_output=True, timeout=30)
    if proc.returncode:
        raise ValueError("Could not establish the ignored repository-output boundary")
    return proc.stdout.strip()


def verify_location(results):
    lexical = Path(results).absolute()
    if ".." in lexical.parts or lexical.is_symlink() or not lexical.is_dir():
        raise ValueError("Results must name an existing regular output directory")
    physical = lexical.resolve()
    repo = Path(git(physical, "rev-parse", "--show-toplevel")).resolve()
    check_ancestors(lexical, repo)
    try:
        physical.relative_to(repo / "outputs")
    except ValueError as exc:
        raise ValueError("Completed results must be beneath repository outputs") from exc
    if physical.parent != repo / "outputs":
        raise ValueError("Expected a direct run folder beneath repository outputs")
    git(repo, "check-ignore", "--quiet", "--", str(physical / "summary.json"))
    return repo, physical


def manifest_hashes(data):
    found = {}
    for line in data.decode("utf-8").splitlines():
        matched = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not matched:
            raise ValueError("Malformed original output checksum manifest")
        expected, name = matched.groups()
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name
                or relative.as_posix() != name or name in found):
            raise ValueError("Unsafe or duplicate checksum-manifest path")
        found[name] = expected
    if not {"summary.json", CSV_NAME} <= set(found):
        raise ValueError("Original checksum manifest does not bind required inputs")
    return found


def finite_number(text, *, blank=False):
    if blank and text == "":
        return None
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Malformed numeric value in per-group table") from exc
    if not math.isfinite(value):
        raise ValueError("Nonfinite value in per-group table")
    return value


def parse_rows(data):
    stream = io.StringIO(data.decode("utf-8"), newline="")
    reader = csv.reader(stream, strict=True)
    if next(reader, None) != COLUMNS:
        raise ValueError("Per-group table header differs from the completed engine schema")
    rows = {mask: {} for mask in MASKS}
    total = 0
    for fields in reader:
        total += 1
        if total > MAX_CSV_ROWS or len(fields) != len(COLUMNS):
            raise ValueError("Per-group table row bound or width is invalid")
        if any(len(text) > 512 for text in fields):
            raise ValueError("Per-group table field exceeds its bound")
        row = dict(zip(COLUMNS, fields))
        mask, identity = row["mask"], row["gene"]
        if mask not in rows or identity in rows[mask]:
            raise ValueError("Unknown mask or duplicate per-group identity")
        if row["source_gene_status"] not in STATUS_NAMES:
            raise ValueError("Unknown source-gene accounting status")
        for name in COUNT_COLUMNS:
            if not re.fullmatch(r"0|[1-9][0-9]*", row[name]):
                raise ValueError("Per-group count must be a nonnegative integer")
            row[name] = int(row[name])
        if row["complete_pair_eligible"] not in {"True", "False"}:
            raise ValueError("Eligibility requires the original explicit boolean encoding")
        row["eligible"] = row["complete_pair_eligible"] == "True"
        row["contrast"] = finite_number(row["contrast"], blank=True)
        row["position_contrast"] = finite_number(row["position_contrast"], blank=True)
        row["weight"] = finite_number(row["weight"])
        if row["eligible"]:
            if (row["source_gene_status"] != "usable_recorded_source_gene_string_only"
                    or row["contrast"] is None or row["position_contrast"] is None
                    or not -2 <= row["contrast"] <= 2
                    or not -1 <= row["position_contrast"] <= 1
                    or row["weight"] <= 0 or row["complete_guide_pairs"] < 1):
                raise ValueError("Eligible per-group row contradicts its status or effect")
        elif (row["weight"] != 0 or row["complete_guide_pairs"] != 0
              or row["contrast"] is not None or row["position_contrast"] is not None):
            raise ValueError("Ineligible group cannot acquire a numerical effect or weight")
        rows[mask][identity] = row
    if set(rows[MASKS[0]]) != set(rows[MASKS[1]]):
        raise ValueError("Masks must retain the same original group-accounting universe")
    return rows


def close(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    return math.isfinite(expected) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-11)


def check_aggregates(summary, rows):
    cross = summary["crossguide"]
    for mask, groups in rows.items():
        reported = cross["masks"][mask]
        selected = [row for row in groups.values() if row["eligible"]]
        n = len(selected)
        if (len(groups) != cross["initial_source_gene_groups_including_missing_value"]
                or sum(row["initial_anchor_wells"] for row in groups.values()) != cross["initial_noncontrol_anchors"]
                or dict(Counter(row["source_gene_status"] for row in groups.values())) != cross["source_gene_group_status_counts"]
                or n != reported["eligible_gene_groups"]
                or sum(row["complete_guide_pairs"] for row in selected) != reported["complete_guide_pairs"]):
            raise ValueError("Per-group eligibility/accounting differs from the preserved summary")
        if any(not close(row["weight"], 1 / n) for row in selected):
            raise ValueError("Expected the frozen equal-source-group weights")
        effect = statistics.fmean(row["contrast"] for row in selected) if n else None
        position = statistics.fmean(row["position_contrast"] for row in selected) if n else None
        if not close(effect, reported["contrast"]) or not close(position, reported["position_contrast"]):
            raise ValueError("Per-group aggregate does not reproduce the preserved effect")
    for identity in rows[MASKS[0]]:
        a, b = rows[MASKS[0]][identity], rows[MASKS[1]][identity]
        for field in ("source_gene_status", "initial_anchor_wells", "initial_sequence_guides",
                      "initial_plates", "finite_anchor_wells", "label_usable_anchor_wells"):
            if a[field] != b[field]:
                raise ValueError("Original group metadata changes across masks")


def quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def distribution(values):
    n = len(values)
    return {
        "group_count": n,
        "mean": statistics.fmean(values) if n else None,
        "median": statistics.median(values) if n else None,
        "positive_group_count": sum(value > 0 for value in values),
        "negative_group_count": sum(value < 0 for value in values),
        "zero_group_count": sum(value == 0 for value in values),
        "fraction_positive": sum(value > 0 for value in values) / n if n else None,
        "quantiles": {str(p): quantile(values, p) for p in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)},
        "quantile_definition": "linear interpolation at (N-1)*probability; descriptive only",
    }


def concentration(values):
    n, total = len(values), math.fsum(values)
    k = min(5, n)
    largest_signed = sorted(values, reverse=True)[:k]
    largest_absolute = sorted(values, key=lambda x: (-abs(x), -x))[:k]
    positive = sorted((x for x in values if x > 0), reverse=True)
    abs_total = math.fsum(abs(x) for x in values)
    leave_one_out = [(total - value) / (n - 1) for value in values] if n > 1 else []
    return {
        "selection_is_post_hoc_descriptive": True,
        "largest_signed_contrasts": {
            "selected_count": k,
            "signed_contribution_to_full_mean": math.fsum(largest_signed) / n if n else None,
            "selection_contains_nonpositive": any(x <= 0 for x in largest_signed),
            "definition": "Largest signed group effects; selected values need not all be positive",
        },
        "largest_absolute_contrasts": {
            "selected_count": k,
            "fraction_of_total_absolute_effect_sum": math.fsum(abs(x) for x in largest_absolute) / abs_total if abs_total else None,
            "signed_contribution_to_full_mean": math.fsum(largest_absolute) / n if n else None,
            "definition": "Groups selected by largest absolute effects, retaining their signs; fraction uses absolute-effect sum, not the possibly cancelling signed mean",
        },
        "largest_positive_contrasts": {
            "selected_count": min(5, len(positive)),
            "fraction_of_total_positive_effect_sum": math.fsum(positive[:5]) / math.fsum(positive) if positive else None,
        },
        "leave_one_group_contribution_out": {
            "count": len(leave_one_out),
            "minimum_mean": min(leave_one_out) if leave_one_out else None,
            "maximum_mean": max(leave_one_out) if leave_one_out else None,
            "all_retained_means_positive": all(x > 0 for x in leave_one_out) if leave_one_out else None,
            "definition": "Remove one group's already computed contribution and renormalize equal group weights; gallery/reference values stay frozen. This does not remove that gene from galleries/references, re-estimate preprocessing or rescore profiles.",
        },
    }


def frozen_plate_omissions(mask_summary):
    pairs = mask_summary["unordered_plate_pairs"]
    if len(pairs) != 6:
        raise ValueError("Expected six preserved physical plate-pair summaries")
    plates = sorted({p for row in pairs for p in (row["plate_a"], row["plate_b"])})
    if len(plates) != 4 or len({tuple(sorted((r["plate_a"], r["plate_b"]))) for r in pairs}) != 6:
        raise ValueError("Physical pair summaries are incomplete or duplicated")
    output = []
    for i, omitted in enumerate(plates, 1):
        kept = [r for r in pairs if omitted not in (r["plate_a"], r["plate_b"])]
        if len(kept) != 3 or any(not close(r["weight"], 1 / 6) for r in kept):
            raise ValueError("Expected frozen equal-weight plate pairs")
        output.append({"anonymous_omitted_plate": f"P{i}",
                       "retained_pair_count": len(kept),
                       "frozen_cohort_mean": statistics.fmean(r["contrast"] for r in kept)})
    return {
        "results": output,
        "definition": "Mean of the three already scored pair summaries not using one plate, on the original four-plate-complete gene cohort. No new three-plate eligibility, refitting, held-out validation or independent experiments are established.",
    }


def compute_diagnostics(summary, rows):
    check_aggregates(summary, rows)
    per_mask = {}
    for mask in MASKS:
        all_rows = list(rows[mask].values())
        eligible = [r for r in all_rows if r["eligible"]]
        values = [r["contrast"] for r in eligible]
        per_mask[mask] = {
            "accounting": {
                "initial_source_groups": len(all_rows), "eligible_source_groups": len(eligible),
                "ineligible_source_groups": len(all_rows) - len(eligible),
                "initial_status_counts": dict(sorted(Counter(r["source_gene_status"] for r in all_rows).items())),
                "ineligible_status_counts": dict(sorted(Counter(r["source_gene_status"] for r in all_rows if not r["eligible"]).items())),
            },
            "morphology": distribution(values),
            "position": distribution([r["position_contrast"] for r in eligible]),
            "concentration": concentration(values),
            "frozen_plate_omissions": frozen_plate_omissions(summary["crossguide"]["masks"][mask]),
        }
    primary = {g for g, row in rows[MASKS[0]].items() if row["eligible"]}
    secondary = {g for g, row in rows[MASKS[1]].items() if row["eligible"]}
    common = sorted(primary & secondary)
    only_primary, only_secondary = sorted(primary - secondary), sorted(secondary - primary)
    paired = summary["crossguide"]["paired_mask_difference"]
    differences = [rows[MASKS[1]][g]["contrast"] - rows[MASKS[0]][g]["contrast"] for g in common]
    if (len(common) != paired["intersection_gene_groups"]
            or len(only_primary) != paired["primary_only_gene_groups"]
            or len(only_secondary) != paired["secondary_only_gene_groups"]
            or not close(statistics.fmean(differences) if differences else None, paired["contrast_difference"])):
        raise ValueError("Matched cohort does not reproduce the preserved paired sensitivity")
    def subset(mask, identities):
        return {
            "morphology": distribution([rows[mask][g]["contrast"] for g in identities]),
            "position": distribution([rows[mask][g]["position_contrast"] for g in identities]),
        }
    return {
        "per_mask": per_mask,
        "mask_cohort_composition": {
            "intersection_groups": len(common),
            "strict_mask_common_groups": subset(MASKS[0], common),
            "relaxed_mask_common_groups": subset(MASKS[1], common),
            "strict_mask_only_groups": subset(MASKS[0], only_primary),
            "relaxed_mask_only_groups": subset(MASKS[1], only_secondary),
            "within_common_group_difference": distribution(differences),
            "interpretation": "Mask populations and reference sets may change. Separate the common-group change from additional-group composition; neither is a causal layout adjustment.",
        },
    }


def inspect(results):
    repo, original = verify_location(results)
    for relative in ("summary.json", "SHA256SUMS", CSV_NAME):
        check_ancestors(original / relative, repo)
    manifest_bytes = bounded_bytes(original / "SHA256SUMS", MAX_MANIFEST_BYTES)
    hashes = manifest_hashes(manifest_bytes)
    summary_bytes = bounded_bytes(original / "summary.json", MAX_SUMMARY_BYTES)
    if digest(summary_bytes) != EXPECTED_SUMMARY_SHA256 or hashes["summary.json"] != EXPECTED_SUMMARY_SHA256:
        raise ValueError("Summary does not match the exact supplied completed result")
    summary = json.loads(summary_bytes)
    if (summary.get("status") != "COMPLETE_EXPLORATORY" or summary.get("source_commit") != EXPECTED_SOURCE
            or summary.get("errors") != {} or summary.get("historical_results_modified") is not False):
        raise ValueError("Unexpected completion, source or historical-result state")
    csv_bytes = bounded_bytes(original / CSV_NAME, MAX_CSV_BYTES)
    if digest(csv_bytes) != hashes[CSV_NAME]:
        raise ValueError("Per-group CSV checksum differs from the preserved original manifest")
    rows = parse_rows(csv_bytes)
    diagnostic = {
        "status": "POST_HOC_DIAGNOSTIC_NOT_RESCORE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": EXPECTED_SOURCE,
        "input_analysis_source_commit": EXPECTED_SOURCE,
        "diagnostic_code_git_commit": None,
        "input_hashes": {"summary_sha256": digest(summary_bytes),
                         "per_group_csv_sha256": digest(csv_bytes),
                         "original_manifest_sha256": digest(manifest_bytes)},
        "diagnostic_code_sha256": digest(Path(__file__).read_bytes()),
        "profiles_read": False, "profile_scores_recomputed": False,
        "historical_results_modified": False, "original_output_directory_modified": False,
        "p_values": None, "confidence_intervals": None,
        "independent_cultures_established": False, "biological_identity_approval_asserted": False,
        "preprocessing": "Existing source-batch-global preprocessing remains frozen on the original four plates; no inductive or held-out normalization is established.",
        "interpretation": "Descriptive concentration and frozen-effect omissions for recorded source-gene groups in one cohort. Source-group contributions and overlapping physical pairs are not independent biological experiments. No source identifiers or private rows are written.",
        **compute_diagnostics(summary, rows),
    }
    # Recheck only the same three original files before creating a sibling output.
    for relative, expected, limit in [("summary.json", digest(summary_bytes), MAX_SUMMARY_BYTES),
                                      (CSV_NAME, digest(csv_bytes), MAX_CSV_BYTES),
                                      ("SHA256SUMS", digest(manifest_bytes), MAX_MANIFEST_BYTES)]:
        check_ancestors(original / relative, repo)
        if digest(bounded_bytes(original / relative, limit)) != expected:
            raise ValueError("Original diagnostic input changed during inspection")
    out = original.parent / ("phase53-concentration." + uuid.uuid4().hex[:12])
    git(repo, "check-ignore", "--quiet", "--", str(out / "concentration-summary.json"))
    if out.exists() or out.is_symlink():
        raise ValueError("Diagnostic output must be a fresh sibling directory")
    check_ancestors(out, repo)
    out.mkdir(mode=0o700)
    payload = (json.dumps(diagnostic, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    (out / "concentration-summary.json").write_bytes(payload)
    (out / "SHA256SUMS").write_text(digest(payload) + "  concentration-summary.json\n")
    return out, diagnostic


def find_results(downloads=None):
    """Read bounded Phase 5.3 receipts only; never scan profiles or other projects."""
    root = Path(downloads) if downloads is not None else Path.home() / "Downloads"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Downloads directory is unavailable or is a symlink")
    candidates = list(root.glob("perturb-lm-phase53.*"))
    if len(candidates) > 256:
        raise ValueError("Too many Phase 5.3 receipt folders for bounded discovery")
    matches = set()
    for folder in candidates:
        if folder.is_symlink() or not folder.is_dir():
            continue
        receipt_path = folder / "status-receipt.json"
        if receipt_path.is_symlink() or not receipt_path.is_file():
            continue
        try:
            receipt = json.loads(bounded_bytes(receipt_path, MAX_SUMMARY_BYTES))
            if receipt.get("status") != "EXPLORATORY_ANALYSIS_COMPLETE" or receipt.get("commit") != EXPECTED_SOURCE:
                continue
            value = receipt.get("output")
            if not isinstance(value, str) or len(value) > 4096:
                continue
            lexical = Path(value)
            if not lexical.is_absolute() or ".." in lexical.parts or lexical.is_symlink():
                continue
            repo = (folder / "repo").resolve()
            check_ancestors(lexical, repo)
            result = lexical.resolve()
            if result.parent != repo / "outputs":
                continue
            check_ancestors(lexical / "summary.json", repo)
            if digest(bounded_bytes(result / "summary.json", MAX_SUMMARY_BYTES)) == EXPECTED_SUMMARY_SHA256:
                matches.add(result)
        except (ValueError, OSError, TypeError, json.JSONDecodeError):
            continue
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching completed Phase 5.3 result; found " + str(len(matches)))
    return next(iter(matches))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--results", type=Path)
    source.add_argument("--find-results", action="store_true", help="Locate the exact completed result from bounded Downloads receipt folders")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        out, diagnostic = inspect(find_results() if args.find_results else args.results)
    except ValueError as error:
        print("STOP: " + str(error) + ". Original results were preserved.", file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError, csv.Error, subprocess.SubprocessError):
        print("STOP: Completed-result identity, integrity, schema or output checks did not pass. Original results were preserved.", file=sys.stderr)
        return 1
    print(diagnostic["status"])
    print("Attach only: " + str(out / "concentration-summary.json"))
    if sys.platform == "darwin":
        try:
            subprocess.run(["open", "-R", str(out / "concentration-summary.json")],
                           check=False, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass  # The completed result remains available at the printed path.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
