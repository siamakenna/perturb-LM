#!/usr/bin/env python3
"""Run the user-authorized exploratory public-cohort analyses, preserving old results."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PLATES = ["BR00116996", "BR00116997", "BR00116998", "BR00116999"]
REVISION = "56845c7d4dc322652952783d91dae0ffef47829f"
STATUS = "COMPLETE_EXPLORATORY"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def verify_source_pins(repo):
    pins = json.loads((SCRIPT_DIR / "SOURCE_PINS.json").read_text())
    if pins.get("schema_version") != 1 or pins.get("repository") != "siamakenna/perturb-LM":
        raise ValueError("Unexpected source-pin manifest")
    expected = {
        "src/perturb_lm/audits/cohort.py", "src/perturb_lm/audits/rotations.py",
        "src/perturb_lm/audits/guide_support.py", "src/perturb_lm/audits/cross_guide_design.py",
    }
    if {entry["path"] for entry in pins["files"]} != expected or len(pins["files"]) != 4:
        raise ValueError("Unexpected design dependency scope")
    for entry in pins["files"]:
        path = repo / entry["path"]
        if path.is_symlink() or sha(path) != entry["sha256"]:
            raise ValueError("Current design dependency differs from its reviewed source pin")
    return pins


def validate_protocol(protocol):
    if (protocol.get("schema_version") != "phase53.authorized_exploratory.v1"
            or protocol.get("status") != "USER_AUTHORIZED_EXPLORATORY_UNREVIEWED_SOURCE_IDENTITIES"
            or protocol.get("source_revision") != REVISION or protocol.get("plates") != PLATES
            or protocol.get("historical_results_modified") is not False
            or protocol.get("previous_reviewed_protocol_replaced") is not False
            or protocol.get("frozen_before_features") is not True):
        raise ValueError("Unexpected exploratory contract")
    expected = protocol.get("expected_capture", {})
    if expected != {"rows": 1536, "features": 904, "physical_plates": 4}:
        raise ValueError("Unexpected fixed public cohort dimensions")


def guarded_output(repo, out):
    repo, out = Path(repo).resolve(), Path(out).absolute()
    if ".." in out.parts:
        raise ValueError("Output paths must not contain parent traversal")
    if out.exists() or out.is_symlink():
        raise ValueError("Output must be a fresh nonexistent directory")
    for part in (out.parent, *out.parent.parents):
        if part.is_symlink():
            raise ValueError("Output ancestors must not be symlinks")
        # macOS may spell this same checkout under /var and /private/var.
        # Stop at the physical repository boundary, while still rejecting
        # symlinks encountered inside it before this boundary comparison.
        if part.resolve() == repo:
            break
    out = out.resolve()
    try:
        out.relative_to(repo / "outputs")
    except ValueError as exc:
        raise ValueError("Output must be beneath this repository's outputs directory") from exc
    probe = subprocess.run(["git", "-C", str(repo), "check-ignore", "--quiet", str(out / "summary.json")], check=False)
    if probe.returncode:
        raise ValueError("Research outputs must remain Git-ignored")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(out, 0o700)
    return repo, out


def finalize_checksums(out):
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_symlink():
            raise ValueError("Unexpected output symlink")
        if path.is_file() and path.name != "SHA256SUMS":
            files.append(path)
    (out / "SHA256SUMS").write_text("".join(
        sha(path) + "  " + path.relative_to(out).as_posix() + "\n" for path in files
    ))


def public_receipt(receipt):
    # No absolute workstation paths, annotation strings or row-level ledgers.
    names = {
        "repository", "revision", "batch", "plates", "cohort_origin",
        "original_twelve_file_cohort_verified", "selected_rows", "feature_count",
        "feature_schema_sha256", "metadata_sha256", "missing_label_rows",
        "labeled_treatment_rows", "labeled_control_rows", "bounds",
        "upstream_normalization_scope", "nonfinite_feature_values_retained",
    }
    return {key: receipt[key] for key in sorted(names) if key in receipt}


def execute(repo, out, *, fetch_public=False, staging=None, authorize_exploratory=False):
    if not authorize_exploratory:
        raise ValueError("Use --authorize-exploratory for the newly authorized provisional endpoint")
    repo = Path(repo).resolve()
    if git(repo, "status", "--porcelain"):
        raise ValueError("Commit the study code and protocol before opening numerical features")
    source_commit = git(repo, "rev-parse", "HEAD")
    pins = verify_source_pins(repo)
    protocol_bytes = (SCRIPT_DIR / "PROTOCOL.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    validate_protocol(protocol)
    repo, out = guarded_output(repo, out)
    source_path = str(repo / "src")
    if source_path not in sys.path:
        sys.path.insert(0, source_path)
    import public_inputs

    if fetch_public == (staging is not None):
        raise ValueError("Choose exactly one of --fetch-public or --staging")
    code_hashes = {p.name: sha(p) for p in sorted(SCRIPT_DIR.glob("*.py"))}
    contract = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit, "protocol": protocol,
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "source_dependencies": pins, "study_python_sha256": code_hashes,
        "coauthor_approval_asserted": False,
        "frozen_before_feature_loading": True,
    }
    contract_path = out / "frozen-analysis-contract.json"
    write_json(contract_path, contract)
    contract_digest = sha(contract_path)
    write_json(out / "RUN_STATUS.json", {"status": "CONTRACT_FROZEN_INPUTS_PENDING"})
    print("Exploratory contract frozen. Preparing only the four pinned public plates...", flush=True)
    try:
        if fetch_public:
            import shutil
            staging = out / "inputs"
            public_inputs.fetch_public_inputs(staging, gh=shutil.which("gh"))
        staging = Path(staging).resolve()
        manifest_digest = sha(staging / "manifest.json")
        # Bind the completed capture before any feature parsing.
        write_json(out / "input-capture-binding.json", {
            "manifest_sha256": manifest_digest, "source_revision": REVISION,
            "input_origin": public_inputs.ORIGIN,
        })
        study = public_inputs.load_study_inputs(staging)
        if sha(staging / "manifest.json") != manifest_digest or sha(contract_path) != contract_digest:
            raise ValueError("Input manifest or frozen contract changed during loading")
        if study["features"].shape != (1536, 904) or len(study["feature_names"]) != 904:
            raise ValueError("The pinned study requires 1536 rows and the unchanged 904-feature schema")
        write_json(out / "input-receipt.json", study["receipt"])
    except Exception as exc:
        write_json(out / "summary.json", {
            "status": "BLOCKED", "source_commit": source_commit,
            "analysis_contract_sha256": contract_digest,
            "stage": "public_input_verification", "error_type": type(exc).__name__,
            "scientific_results_computed": False,
            "message": "Public capture or input verification did not complete. Keep this folder; no substitute data were used.",
        })
        write_json(out / "RUN_STATUS.json", {"status": "BLOCKED"})
        finalize_checksums(out)
        raise RuntimeError("Public input preparation failed; see the local summary and retained files") from exc

    from crossguide import analyze_crossguide
    from query_audit import analyze_query_information
    from report import render_report

    results, errors = {}, {}
    print("Running morphology/position concordance and query-information audit in parallel...", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            "crossguide": pool.submit(analyze_crossguide, study["metadata"], study["features"]),
            "query_information": pool.submit(analyze_query_information, study["metadata"]),
        }
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                errors[name] = {"error_type": type(exc).__name__, "message": "Analysis failed; no value was substituted."}
    private = out / "PRIVATE"
    private.mkdir(mode=0o700)
    for analysis_name, result in results.items():
        for name, value in result.items():
            if name.startswith("private_"):
                value.to_csv(private / (analysis_name + "_" + name + ".csv"), index=False)
    summary = {
        "status": "PARTIAL_EXPLORATORY" if errors else STATUS,
        "source_commit": source_commit, "analysis_contract_sha256": contract_digest,
        "input_capture_manifest_sha256": manifest_digest,
        "input_receipt": public_receipt(study["receipt"]),
        "crossguide": results.get("crossguide", {}).get("summary"),
        "query_information": results.get("query_information", {}).get("summary"),
        "errors": errors,
        "interpretation": "Authorized exploratory descriptions of one four-plate cohort; source annotations and preprocessing are not biologically validated. No confidence intervals, p-values or independent replication are asserted.",
        "historical_results_modified": False, "real_outputs_automatically_published": False,
    }
    if sha(contract_path) != contract_digest or sha(staging / "manifest.json") != manifest_digest:
        raise ValueError("Input capture or protocol changed during analysis")
    if code_hashes != {p.name: sha(p) for p in sorted(SCRIPT_DIR.glob("*.py"))}:
        raise ValueError("Study code changed during analysis")
    write_json(out / "analysis-results-pending.json", {
        **summary, "status": "ANALYSES_FINISHED_REPORT_PENDING"
    })
    write_json(out / "RUN_STATUS.json", {"status": "ANALYSES_FINISHED_REPORT_PENDING"})
    render_report(out, summary, results.get("crossguide"), results.get("query_information"))
    write_json(out / "summary.json", summary)
    write_json(out / "RUN_STATUS.json", {"status": summary["status"]})
    finalize_checksums(out)
    print(summary["status"] + ". Report: " + str(out / "report.html"), flush=True)
    print("Aggregate summary: " + str(out / "summary.json"), flush=True)
    print("Row-level tables remain local under PRIVATE/.", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fetch-public", action="store_true")
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--authorize-exploratory", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        summary = execute(args.repo, args.out, fetch_public=args.fetch_public,
                          staging=args.staging, authorize_exploratory=args.authorize_exploratory)
    except Exception as exc:
        print("STOP: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0 if summary["status"] == STATUS else 2)


if __name__ == "__main__":
    main()
