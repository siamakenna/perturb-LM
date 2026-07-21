#!/usr/bin/env python3
"""Check public website summary numbers against the readiness report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "apps" / "web" / "src" / "data" / "project-summary.json"
READINESS_PATH = ROOT / "docs" / "PHASE3B_FOUNDATION_READINESS.md"
PHASE3C_PATH = ROOT / "docs" / "PHASE3C_TEXT_PROFILE_ALIGNMENT.md"


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text())
    readiness = READINESS_PATH.read_text()
    phase3c = PHASE3C_PATH.read_text()
    errors: list[str] = []

    expected = {
        "profileCount": _extract_int(readiness, r"\| profile rows \| ([0-9,]+) \|"),
        "featureCount": _extract_int(
            readiness,
            r"\| usable numeric morphology features \| ([0-9,]+) \|",
        ),
        "queryCount": _extract_int(readiness, r"total queries: ([0-9,]+)"),
        "lexicalBaselineMap": _extract_float(
            readiness,
            r"\| identifier-stripped TF-IDF \| ([0-9.]+) \|",
        ),
        "ciLow": _extract_float(
            readiness,
            r"\| identifier-stripped TF-IDF \| mAP \| [0-9.]+ \| ([0-9.]+) to",
        ),
        "ciHigh": _extract_float(
            readiness,
            r"\| identifier-stripped TF-IDF \| mAP \| [0-9.]+ \| [0-9.]+ to ([0-9.]+) \|",
        ),
        "randomMap": _extract_float(readiness, r"\| random \| ([0-9.]+) \|"),
        "shuffledMap": _extract_float(readiness, r"\| shuffled label \| ([0-9.]+) \|"),
        "selectedEncoder": _extract_text(phase3c, r"- Model: `([^`]+)`"),
        "selectedEncoderRevision": _extract_text(phase3c, r"- Pinned revision: `([^`]+)`"),
    }

    _compare(errors, "profileCount", summary.get("profileCount"), expected["profileCount"])
    _compare(errors, "featureCount", summary.get("featureCount"), expected["featureCount"])
    _compare(errors, "queryCount", summary.get("queryCount"), expected["queryCount"])
    _compare_float(
        errors,
        "lexicalBaselineMap",
        summary.get("lexicalBaselineMap"),
        expected["lexicalBaselineMap"],
    )
    ci = summary.get("confidenceInterval", {})
    _compare_float(errors, "confidenceInterval.low", ci.get("low"), expected["ciLow"])
    _compare_float(errors, "confidenceInterval.high", ci.get("high"), expected["ciHigh"])

    model_status = str(summary.get("learnedModelStatus", "")).strip().lower()
    claim_status = str(summary.get("currentClaimStatus", "")).lower()
    if model_status != "pending":
        errors.append("learnedModelStatus must remain pending until real model results exist.")
    if str(summary.get("phase3cImplementationStatus", "")).strip().lower() != "ready":
        errors.append("phase3cImplementationStatus must be ready after infrastructure merge.")
    if str(summary.get("projectedModelStatus", "")).strip().lower() != "pending":
        errors.append("projectedModelStatus must remain pending until real projection results exist.")
    selected_encoder = summary.get("selectedEncoder", {})
    _compare(errors, "selectedEncoder.model", selected_encoder.get("model"), expected["selectedEncoder"])
    _compare(
        errors,
        "selectedEncoder.pinnedRevision",
        selected_encoder.get("pinnedRevision"),
        expected["selectedEncoderRevision"],
    )
    if str(selected_encoder.get("runStatus", "")).strip().lower() != "pending":
        errors.append("selectedEncoder.runStatus must remain pending until real encoder results exist.")
    if str(summary.get("heldOutBatchStatus", "")).strip().lower() != "unavailable":
        errors.append("heldOutBatchStatus must remain unavailable until a second batch exists.")
    if str(summary.get("syntheticDisclaimer", "")).strip() != (
        "Illustrative interface demo — not real model output"
    ):
        errors.append("syntheticDisclaimer changed from the required public-safe wording.")
    completed_terms = ["completed model", "model result achieved", "learned model outperforms"]
    if model_status == "pending" and any(term in claim_status for term in completed_terms):
        errors.append("currentClaimStatus implies a completed model result while status is pending.")
    methods = {str(item.get("key")): item for item in summary.get("methodComparison", [])}
    _compare_float(errors, "methodComparison.random.map", methods.get("random", {}).get("map"), expected["randomMap"])
    _compare_float(
        errors,
        "methodComparison.shuffled_label.map",
        methods.get("shuffled_label", {}).get("map"),
        expected["shuffledMap"],
    )
    _compare_float(
        errors,
        "methodComparison.identifier_stripped_tfidf.map",
        methods.get("identifier_stripped_tfidf", {}).get("map"),
        expected["lexicalBaselineMap"],
    )
    for key, item in methods.items():
        is_pending_model = key in {
            "frozen_biomedbert",
            "linear_projection",
            "replicate_consensus",
            "held_out_batch",
        }
        if is_pending_model:
            if item.get("hasResult") is not False:
                errors.append(f"Pending method {key} must have hasResult=false.")
            if item.get("map") is not None or item.get("ciLow") is not None or item.get("ciHigh") is not None:
                errors.append(f"Pending method {key} must not expose numeric scores.")

    serialized = json.dumps(summary, sort_keys=True).lower()
    forbidden = ["metadata_target_sequence", "brdn", "/users/", "data/raw", ".npy", ".pkl"]
    for token in forbidden:
        if token in serialized:
            errors.append(f"Public summary contains forbidden token: {token}")

    if errors:
        print("Public copy consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Public copy consistency check passed.")


def _extract_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Pattern not found: {pattern}")
    return int(match.group(1).replace(",", ""))


def _extract_float(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Pattern not found: {pattern}")
    return float(match.group(1))


def _extract_text(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Pattern not found: {pattern}")
    return match.group(1)


def _compare(errors: list[str], name: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        errors.append(f"{name} differs: observed {observed!r}, expected {expected!r}.")


def _compare_float(errors: list[str], name: str, observed: Any, expected: float) -> None:
    try:
        value = float(observed)
    except (TypeError, ValueError):
        errors.append(f"{name} is not numeric: {observed!r}.")
        return
    if round(value, 4) != round(expected, 4):
        errors.append(f"{name} differs: observed {value!r}, expected {expected!r}.")


if __name__ == "__main__":
    main()
