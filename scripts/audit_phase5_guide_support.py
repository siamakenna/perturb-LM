#!/usr/bin/env python3
"""Local metadata-only support census; no model, score, query, or minimum threshold (#30,#52)."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from pathlib import Path

from plan_phase5_1_rotations import guarded_output

from perturb_lm.audits.cohort import checksum
from perturb_lm.audits.guide_support import IdentityError, support_census
from perturb_lm.audits.json_inputs import read_json_snapshot
from perturb_lm.audits.support_inputs import VerificationError, verify_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path.cwd(),
        help="Validation/context JSON root within invocation directory (default: same directory)",
    )
    parser.add_argument(
        "--validation",
        type=Path,
        required=True,
        help="Local aggregate-only evidence of checks actually executed",
    )
    parser.add_argument(
        "--repository-context",
        type=Path,
        required=True,
        help="Local aggregate-only inspected repository snapshot",
    )
    args = parser.parse_args()
    os.umask(0o077)
    repository = Path(__file__).resolve().parents[1]
    out = guarded_output(args.out, repository)
    validation = read_json_snapshot(args.validation, root=args.evidence_root)
    repository_context = read_json_snapshot(args.repository_context, root=args.evidence_root)
    summary = {
        "schema_version": 1,
        "evidence_kind": "actual_local_metadata_census",
        "scientific_approval": False,
        "retrieval_scores_computed": False,
        "predictive_queries_generated": False,
        "feature_values_parsed": False,
        "code_git_sha": subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
        ).strip(),
        "tracked_or_untracked_code_changes_present": bool(
            subprocess.check_output(
                ["git", "-C", str(repository), "status", "--porcelain"], text=True
            ).strip()
        ),
        "implementation_sha256": {
            p: checksum(repository / p)
            for p in (
                "scripts/audit_phase5_guide_support.py",
                "src/perturb_lm/audits/guide_support.py",
                "src/perturb_lm/audits/json_inputs.py",
                "src/perturb_lm/audits/support_inputs.py",
                "src/perturb_lm/audits/rotations.py",
                "src/perturb_lm/audits/cohort.py",
            )
        },
        "runtime": {"python": platform.python_version()},
        "validation": validation.value,
        "validation_evidence_sha256": validation.sha256,
        "repository_context": repository_context.value,
        "repository_context_sha256": repository_context.sha256,
    }
    try:
        mapping, annotations, evidence, inputs = verify_inputs(args.audit_root, args.data_root)
        summary["verification"] = evidence
        summary["support_census"] = support_census(mapping, annotations)
        summary["all_input_manifest_hashes_unchanged_after_census"] = all(
            checksum(p) == evidence["input_manifest_sha256"][k] for k, p in inputs.items()
        )
        if not summary["all_input_manifest_hashes_unchanged_after_census"]:
            raise VerificationError(evidence)
        summary["status"] = "COMPLETED_DESCRIPTIVE_METADATA_AUDIT"
    except VerificationError as exc:
        summary.update(status="STOPPED_INPUT_VERIFICATION", verification=exc.evidence)
    except IdentityError as exc:
        summary.update(status="STOPPED_SELECTED_IDENTITY_CONFLICT", identity_conflicts=exc.counts)
    except ValueError as exc:
        # Known validators provide field-level descriptions, never row values or paths.
        summary.update(status="STOPPED_VALIDATION", validation_failure=str(exc))
    summary["preprocessing_and_replication_uncertainties"] = {
        "input_kind": "normalized_feature_select_negcon_batch",
        "preserved_source_README_evidence": (
            "CellProfiler well aggregation; Pycytominer annotation, whole-plate "
            "and negative-control "
            "normalization variants, MAD robustization, invariant/redundant feature filtering. "
            "README lists plate feature-selection variants; it does not document the exact "
            "selected negcon_batch artifact's fitted populations or parameters."
        ),
        "exact_normalization_fit_population": "unknown for these artifact bytes",
        "exact_feature_selection_fit_population_and_parameters": "unknown",
        "same_904_feature_header_proves_train_only_fit": False,
        "inductive_preprocessing_certified": False,
        "new_scaler_can_undo_upstream_fit": False,
        "culture_independence": "not established",
        "guide_efficacy_and_off_target_effects": "not measured",
        "reviewed_stable_gene_identity": "not provided",
        "WGA_anomaly": "retained in both endpoints and spatial sensitivities",
        "one_batch": "no independent cross-batch inference",
        "F10_guard": (
            "unchanged; no rendering or encoding executed; any future exception requires review"
        ),
        "rotations": "12 overlapping assignments of four plates, not 12 independent experiments",
    }
    summary["smallest_defensible_next_experiment"] = {
        "proposal_only": True,
        "next_step": (
            "Review the source-gene/different-sequence identity ledger locally and decide whether "
            "its per-assignment capacity supports a prespecified cross-guide morphology agreement "
            "diagnostic against matched different-gene controls. Keep exact "
            "reagent recovery separate. "
            "Resolve upstream preprocessing interpretation before a scored experiment."
        ),
        "remaining_decisions": {
            "Makenna": (
                "Choose exact-reagent versus provisional cross-guide question and "
                "study scope; authorize any subsequent scoring separately"
            ),
            "Claire": (
                "Review stable gene/guide identity, targeting/efficacy evidence, WGA "
                "inclusion, culture independence, meaningful unit and minimum "
                "evidence; source strings are not biological relevance approval"
            ),
            "Adam": (
                "Review per-assignment denominators, both spatial sensitivities, "
                "training exposure and upstream normalization/selection scope; "
                "preserve the production guard"
            ),
        },
        "scientific_minimum_thresholds": "not chosen; synthetic 3/2 settings not used",
    }
    out.mkdir(parents=True, exist_ok=False)
    target = out / "metadata-support-summary.json"
    with target.open("x") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    with (out / "SHA256SUMS").open("x") as stream:
        stream.write(f"{checksum(target)}  {target.name}\n")
    print(summary["status"])
    if summary["status"] != "COMPLETED_DESCRIPTIVE_METADATA_AUDIT":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
