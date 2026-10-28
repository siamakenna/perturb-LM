#!/usr/bin/env python3
"""Offline, post hoc comparison of two exact completed source-annotation studies.

Reads only original summaries, output manifests, frozen contracts and private
gene/observation result tables. Never opens profiles or recomputes scores.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
from itertools import permutations
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import uuid

import inspect_concentration as common

PINS = {
    "u2os": {"source": "589ad24f14eec0ac8b726f37ba89abef1a5316b2",
             "summary": "1d325458adfffd4488869a6e5c2b19da65ecbf9adb3aa1bc8028b3b1f72ed79e"},
    "a549": {"source": "c28bd56f56771055e3cc5c7e84bcff0841e76190",
             "summary": "8a431da94933685ec4099a40aae6d8522b0d448dab4d009950ae37f75527a99e"},
}
FEATURE_SCHEMA = "7939910c0370fcba96c258391d1990fe8d8b47b1308494826925b6fa444ed368"
ENGINE_SHA = "1973668934cea93818c1570380a69ccbc3284f4fc26bdc7f51bb04c9ba8df420"
QUERY_SHA = "c5c1707a4974e3fefe09de0c71975423ef4902de93852155e9977942ee84051d"
GENES = "PRIVATE/crossguide_private_genes.csv"
OBSERVATIONS = "PRIVATE/crossguide_private_observations.csv"
CONTRACT = "frozen-analysis-contract.json"
OBS_COLUMNS = [
    "mask", "row_id", "gene", "guide", "partner_guide", "anchor_plate",
    "gallery_plate", "well", "positive_mean_cosine", "reference_mean_cosine",
    "contrast", "position_positive_mean", "position_reference_mean", "position_contrast",
    "positive_wells", "reference_wells", "reference_guides", "reference_genes",
    "weight", "complete_pair_eligible",
]
LIMITS = {"summary.json": 256 * 1024, "SHA256SUMS": 4 * 1024 * 1024,
          GENES: 2 * 1024 * 1024, OBSERVATIONS: 16 * 1024 * 1024,
          CONTRACT: 2 * 1024 * 1024}


def location(results):
    lexical = Path(results).absolute()
    if ".." in lexical.parts or lexical.is_symlink() or not lexical.is_dir():
        raise ValueError("Results must be an existing regular output directory")
    physical = lexical.resolve()
    repo = Path(common.git(physical, "rev-parse", "--show-toplevel")).resolve()
    common.check_ancestors(lexical, repo)
    try:
        physical.relative_to(repo / "outputs")
    except ValueError as exc:
        raise ValueError("Completed results must remain under repository outputs") from exc
    common.git(repo, "check-ignore", "--quiet", "--", str(physical / "summary.json"))
    return repo, physical


def read_result(name, results):
    repo, original = location(results)
    raw = {}
    for relative, limit in LIMITS.items():
        common.check_ancestors(original / relative, repo)
        raw[relative] = common.bounded_bytes(original / relative, limit)
    hashes = common.manifest_hashes(raw["SHA256SUMS"])
    if not {"summary.json", GENES, OBSERVATIONS, CONTRACT} <= hashes.keys():
        raise ValueError("Original manifest does not bind all diagnostic inputs")
    for relative in ("summary.json", GENES, OBSERVATIONS, CONTRACT):
        if common.digest(raw[relative]) != hashes[relative]:
            raise ValueError("Diagnostic input checksum differs from its original manifest")
    if common.digest(raw["summary.json"]) != PINS[name]["summary"]:
        raise ValueError("Summary is not the exact uploaded completed result")
    summary = json.loads(raw["summary.json"])
    if (summary.get("source_commit") != PINS[name]["source"]
            or summary.get("status") != "COMPLETE_EXPLORATORY"
            or summary.get("errors") != {}
            or summary.get("historical_results_modified") is not False):
        raise ValueError("Completed result has an unexpected source or completion state")
    receipt = summary.get("input_receipt", {})
    if receipt.get("feature_count") != 904 or receipt.get("feature_schema_sha256") != FEATURE_SCHEMA:
        raise ValueError("Ordered feature schema differs from the verified shared schema")
    if receipt.get("upstream_normalization_scope") != "source_batch_global":
        raise ValueError("Unexpected source preprocessing provenance")
    contract = json.loads(raw[CONTRACT])
    code = contract.get("study_python_sha256", {})
    if (common.digest(raw[CONTRACT]) != summary.get("analysis_contract_sha256")
            or contract.get("source_commit") != PINS[name]["source"]
            or code.get("crossguide.py") != ENGINE_SHA or code.get("query_audit.py") != QUERY_SHA):
        raise ValueError("Frozen source/engine/query contract does not match the completed study")
    plates = receipt.get("plates")
    if not isinstance(plates, list) or len(plates) != 4 or len(set(plates)) != 4:
        raise ValueError("Expected four unique recorded plates in each context")
    genes = common.parse_rows(raw[GENES])
    native = common.compute_diagnostics(summary, genes)
    pairs = observations(raw[OBSERVATIONS], genes, summary, plates)
    return {"repo": repo, "original": original, "raw": raw, "summary": summary,
            "genes": genes, "pairs": pairs, "native": native,
            "hashes": {relative: common.digest(data) for relative, data in raw.items()}}


def integer(value):
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError("Observation counts require nonnegative integers")
    return int(value)


def observations(data, genes, summary, plates):
    reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
    if next(reader, None) != OBS_COLUMNS:
        raise ValueError("Observation schema differs from the completed scoring engine")
    selected = {mask: defaultdict(list) for mask in common.MASKS}
    seen, anchor_identity, row_identity = set(), {}, {}
    count = 0
    for values in reader:
        count += 1
        if count > 25000 or len(values) != len(OBS_COLUMNS) or any(len(v) > 512 for v in values):
            raise ValueError("Observation row, field or width bound exceeded")
        row = dict(zip(OBS_COLUMNS, values))
        mask = row["mask"]
        if mask not in selected or row["gene"] not in genes[mask]:
            raise ValueError("Unknown observation mask or source-gene accounting identity")
        if (row["anchor_plate"] not in plates or row["gallery_plate"] not in plates
                or row["anchor_plate"] == row["gallery_plate"]
                or not re.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])", row["well"])):
            raise ValueError("Observation has invalid physical plate/well metadata")
        if (not row["row_id"] or any(not re.fullmatch(r"seq_sha256:[0-9a-f]{64}", row[key])
                                      for key in ("guide", "partner_guide"))
                or row["guide"] == row["partner_guide"]):
            raise ValueError("Observation guide or row identity is invalid")
        key = tuple(row[field] for field in ("mask", "gene", "guide", "partner_guide", "anchor_plate", "gallery_plate", "well"))
        if key in seen:
            raise ValueError("Duplicate physical comparison observation")
        seen.add(key)
        physical = (row["anchor_plate"], row["well"])
        identity = (row["row_id"], row["gene"], row["guide"])
        if (physical in anchor_identity and anchor_identity[physical] != identity
                or row["row_id"] in row_identity and row_identity[row["row_id"]] != physical):
            raise ValueError("Observation anchor identity changes across comparisons")
        anchor_identity[physical], row_identity[row["row_id"]] = identity, physical
        for field in ("positive_mean_cosine", "reference_mean_cosine", "contrast",
                      "position_positive_mean", "position_reference_mean", "position_contrast", "weight"):
            row[field] = common.finite_number(row[field])
        if (not all(-1 - 1e-12 <= row[k] <= 1 + 1e-12 for k in ("positive_mean_cosine", "reference_mean_cosine"))
                or not all(-1e-12 <= row[k] <= 1 + 1e-12 for k in ("position_positive_mean", "position_reference_mean"))
                or not common.close(row["contrast"], row["positive_mean_cosine"] - row["reference_mean_cosine"])
                or not common.close(row["position_contrast"], row["position_positive_mean"] - row["position_reference_mean"])):
            raise ValueError("Observation scores contradict the frozen difference definition")
        for field in ("positive_wells", "reference_wells", "reference_guides", "reference_genes"):
            row[field] = integer(row[field])
        if (row["positive_wells"] < 1 or not 1 <= row["reference_genes"] <= row["reference_guides"] <= row["reference_wells"]):
            raise ValueError("Observation has no valid positive/reference accounting")
        if row["complete_pair_eligible"] not in {"True", "False"}:
            raise ValueError("Observation eligibility must use the original explicit boolean")
        eligible = row["complete_pair_eligible"] == "True"
        if row["weight"] < 0 or eligible != (row["weight"] > 0):
            raise ValueError("Observation eligibility contradicts its canonical weight")
        if eligible:
            if not genes[mask][row["gene"]]["eligible"]:
                raise ValueError("Eligible observation belongs to an ineligible source group")
            selected[mask][row["gene"]].append(row)

    result = {mask: {} for mask in common.MASKS}
    for mask, grouped in selected.items():
        expected_groups = {gene for gene, row in genes[mask].items() if row["eligible"]}
        if set(grouped) != expected_groups:
            raise ValueError("Observation groups differ from the original eligible groups")
        if sum(len(v) for v in grouped.values()) != summary["crossguide"]["masks"][mask]["eligible_observations"]:
            raise ValueError("Eligible observation count differs from the original summary")
        for gene, values in grouped.items():
            pairs = {tuple(sorted((r["guide"], r["partner_guide"]))) for r in values}
            row = genes[mask][gene]
            weight = math.fsum(r["weight"] for r in values)
            if (len(pairs) != row["complete_guide_pairs"] or not common.close(weight, row["weight"])
                    or not common.close(math.fsum(r["weight"] * r["contrast"] for r in values) / weight, row["contrast"])
                    or not common.close(math.fsum(r["weight"] * r["position_contrast"] for r in values) / weight, row["position_contrast"])):
                raise ValueError("Observation guide pairs, weights or means do not reproduce the per-group table")
            for pair in pairs:
                observations_for_pair = [r for r in values if tuple(sorted((r["guide"], r["partner_guide"]))) == pair]
                cells = Counter((r["anchor_plate"], r["gallery_plate"], r["guide"]) for r in observations_for_pair)
                required = {(p, q, guide) for p, q in permutations(plates, 2) for guide in pair}
                if set(cells) != required:
                    raise ValueError("A claimed complete pair lacks an original plate/guide direction")
                for observation in observations_for_pair:
                    cell = (observation["anchor_plate"], observation["gallery_plate"], observation["guide"])
                    expected_weight = 1 / len(grouped) / len(pairs) / 12 / 2 / cells[cell]
                    if not common.close(observation["weight"], expected_weight):
                        raise ValueError("Observation weights differ from the frozen balanced hierarchy")
            result[mask][gene] = pairs
    return result


def ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average = (start + 1 + end) / 2
        for index in ordered[start:end]:
            result[index] = average
        start = end
    return result


def correlation(a, b):
    if len(a) != len(b):
        raise ValueError("Correlation inputs must have equal lengths")
    if len(a) < 2:
        return None
    ac, bc = statistics.fmean(a), statistics.fmean(b)
    da, db = [v - ac for v in a], [v - bc for v in b]
    denominator = math.sqrt(math.fsum(v * v for v in da) * math.fsum(v * v for v in db))
    return max(-1.0, min(1.0, math.fsum(x * y for x, y in zip(da, db)) / denominator)) if denominator else None


def matched(contexts):
    output = {}
    a, b = contexts["u2os"], contexts["a549"]
    for mask in common.MASKS:
        ga, gb = set(a["pairs"][mask]), set(b["pairs"][mask])
        shared = ga & gb
        same = sorted(gene for gene in shared if a["pairs"][mask][gene] == b["pairs"][mask][gene])
        va = [a["genes"][mask][gene]["contrast"] for gene in same]
        vb = [b["genes"][mask][gene]["contrast"] for gene in same]
        signs = Counter(("positive" if x > 0 else "negative" if x < 0 else "zero",
                         "positive" if y > 0 else "negative" if y < 0 else "zero") for x, y in zip(va, vb))
        output[mask] = {
            "u2os_eligible_source_groups": len(ga), "a549_eligible_source_groups": len(gb),
            "shared_literal_gene_groups": len(shared), "identical_complete_guide_pair_sets": len(same),
            "shared_gene_groups_held_for_different_guide_pair_sets": len(shared) - len(same),
            "u2os_only_eligible_source_groups": len(ga - gb), "a549_only_eligible_source_groups": len(gb - ga),
            "u2os_matched_distribution": common.distribution(va),
            "a549_matched_distribution": common.distribution(vb),
            "a549_minus_u2os_matched_distribution": common.distribution([y - x for x, y in zip(va, vb)]),
            "pearson_descriptive": correlation(va, vb),
            "spearman_descriptive_average_exact_tie_ranks": correlation(ranks(va), ranks(vb)),
            "sign_counts_u2os_then_a549": {x + "_" + y: signs[(x, y)] for x in ("positive", "negative", "zero") for y in ("positive", "negative", "zero")},
            "matching_policy": "Exact literal source-gene identity and identical unordered sets of complete recorded DNA-hash guide pairs; changed-pair groups are held, not partially reweighted.",
        }
    return output


def discover(downloads=None):
    """Discover bounded completed receipts without a machine-specific folder."""
    root = Path(downloads) if downloads is not None else Path.home() / "Downloads"
    u2os = common.find_results(root)
    folders = list(root.glob("perturb-lm-phase53-a549.*"))
    if len(folders) > 256:
        raise ValueError("Too many A549 receipt folders; provide explicit result paths")
    matches = set()
    for folder in folders:
        if folder.is_symlink() or not folder.is_dir():
            continue
        repo = (folder / "repo").resolve()
        receipt = folder / "repo/outputs/phase53-a549-rowfix-v2/status-receipt.json"
        try:
            common.check_ancestors(receipt, repo)
            data = json.loads(common.bounded_bytes(receipt, common.MAX_SUMMARY_BYTES))
            if (data.get("status") != "EXPLORATORY_ANALYSIS_COMPLETE"
                    or data.get("commit") != PINS["a549"]["source"]
                    or not isinstance(data.get("completed_output"), str)):
                continue
            out = Path(data["completed_output"])
            if not out.is_absolute() or ".." in out.parts:
                continue
            common.check_ancestors(out, repo)
            out.resolve().relative_to(receipt.parent.resolve())
            common.check_ancestors(out / "summary.json", repo)
            if common.digest(common.bounded_bytes(out / "summary.json", common.MAX_SUMMARY_BYTES)) == PINS["a549"]["summary"]:
                matches.add(out.resolve())
        except (OSError, ValueError, TypeError):
            continue
    if len(matches) != 1:
        raise ValueError("Expected one matching completed A549 result; provide explicit result paths")
    return u2os, next(iter(matches))


def compare(u2os_results, a549_results):
    contexts = {name: read_result(name, value) for name, value in (("u2os", u2os_results), ("a549", a549_results))}
    diagnostics = {
        "status": "POST_HOC_CONTEXT_DIAGNOSTIC_NOT_RESCORE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha256": common.digest(Path(__file__).read_bytes()),
        "utility_code_sha256": common.digest(Path(common.__file__).read_bytes()),
        "input_sources": {name: {"analysis_source_commit": PINS[name]["source"], "input_hashes": value["hashes"]} for name, value in contexts.items()},
        "ordered_904_feature_schema_identical": True,
        "ordered_feature_schema_sha256": FEATURE_SCHEMA,
        "frozen_scoring_engine_and_query_audit_identical": True,
        "native_context_diagnostics": {name: value["native"] for name, value in contexts.items()},
        "matched_context_comparison": matched(contexts),
        "profiles_read": False, "profile_scores_recomputed": False,
        "historical_results_modified": False, "original_outputs_modified": False,
        "github_publication_verified": False,
        "p_values": None, "confidence_intervals": None,
        "independent_biological_replication_established": False,
        "biological_identity_approval_asserted": False,
        "causal_cell_context_effect_estimated": False,
        "interpretation": "Post hoc descriptive agreement of frozen source-annotation group contributions in two recorded cell contexts from the same source batch. Matching strings and recorded DNA-hash pairs do not validate stable gene identity, guide efficacy or independent cultures. Gallery/reference populations remain context-specific and can differ with missing profiles; they are not matched by this diagnostic. Cell context is entangled with acquisition/staining differences. Source-batch-global preprocessing remains unverified; matching feature names does not establish train-only fitting. Correlations and sign counts summarize fixed dependent source groups without inferential tests. Frozen contribution omissions do not delete gallery genes or rescore profiles. Native coverage is conditional on observed profiles; the A549 absence remains of unknown cause.",
    }
    for context in contexts.values():
        for relative, expected in context["hashes"].items():
            path = context["original"] / relative
            common.check_ancestors(path, context["repo"])
            if common.digest(common.bounded_bytes(path, LIMITS[relative])) != expected:
                raise ValueError("Original diagnostic input changed during inspection")
    reference = contexts["a549"]
    out = reference["original"].parent / ("context-agreement." + uuid.uuid4().hex[:12])
    common.check_ancestors(out, reference["repo"])
    common.git(reference["repo"], "check-ignore", "--quiet", "--", str(out / "context-agreement-summary.json"))
    if out.exists() or out.is_symlink():
        raise ValueError("Diagnostic output must be a fresh ignored sibling directory")
    out.mkdir(mode=0o700)
    payload = (json.dumps(diagnostics, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    (out / "context-agreement-summary.json").write_bytes(payload)
    (out / "SHA256SUMS").write_text(common.digest(payload) + "  context-agreement-summary.json\n")
    return out, diagnostics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--u2os-results", type=Path)
    parser.add_argument("--a549-results", type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if (args.u2os_results is None) != (args.a549_results is None):
            raise ValueError("Provide both result paths, or neither for bounded receipt discovery")
        u2os, a549 = discover() if args.u2os_results is None else (args.u2os_results, args.a549_results)
        out, diagnostic = compare(u2os, a549)
    except ValueError as exc:
        print("STOP: " + str(exc) + ". Original results were preserved.", file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError, csv.Error, subprocess.SubprocessError):
        print("STOP: Input identity, integrity, schema or output checks failed. Original results were preserved.", file=sys.stderr)
        return 1
    print(diagnostic["status"])
    print("Attach only: " + str(out / "context-agreement-summary.json"))
    if sys.platform == "darwin":
        try:
            subprocess.run(["open", "-R", str(out / "context-agreement-summary.json")], check=False,
                           capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
