#!/usr/bin/env python3
"""Run one implemented synthetic examination; never submit a job or a model matrix."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from run_phase4_acceptance import git, junit_counts, run_logged, stage_status

EXECUTABLE = {
    "installed_package": ["tests/test_pixel_installed.py"],
    "metadata_blindness": [
        "tests/test_pixel_workflow.py::test_external_labels_and_ids_cannot_change_features_or_distances"
    ],
    "filename_independence": [
        "tests/test_pixel_workflow.py::test_renamed_decoded_tiffs_produce_identical_features_and_distances"
    ],
    "pixel_sensitivity": [
        "tests/test_pixel_workflow.py::test_controlled_pixel_changes_have_expected_measurement_effects"
    ],
    "statistical_stability": ["tests/test_paired_treatment_bootstrap.py"],
}


def manifest(path):
    payload = json.loads(path.read_text())
    entries = payload["examinations"]
    ids = [entry["id"] for entry in entries]
    implemented = {e["id"] for e in entries if e["status"] == "implemented_synthetic"}
    if payload["schema_version"] != 1 or len(ids) != 10 or len(set(ids)) != 10:
        raise ValueError("Expected ten distinct examinations in manifest version 1")
    if implemented != set(EXECUTABLE) or payload["submission_authorized"]:
        raise ValueError("Manifest and reviewed runnable examinations differ")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--examination", choices=sorted(EXECUTABLE), required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    root, out = args.repo.resolve(), args.out.resolve()
    if args.timeout <= 0 or args.timeout > 1800 or out.exists() or out.is_relative_to(root):
        parser.error("Use a new output outside the checkout and timeout in 1..1800 seconds")
    if git(root, "status", "--porcelain"):
        parser.error("Use a clean committed source checkout")
    source = git(root, "rev-parse", "HEAD")
    plan = root / "configs/phase4_examinations_v1.json"
    manifest(plan)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PYTEST"))}
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    # Reject a stale editable installation from some other checkout.
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "from pathlib import Path; import perturb_lm; "
            f"source = Path({str(root / 'src')!r}); "
            "assert Path(perturb_lm.__file__).resolve().is_relative_to(source)",
        ],
        cwd=root,
        env=env,
        check=True,
    )
    os.umask(0o077)
    out.mkdir(parents=True)
    env["HF_HOME"] = str(out / "empty-model-cache")
    report = {
        "schema_version": 1,
        "source_commit": source,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "examination": args.examination,
        "scope": "synthetic_software",
        "overall": "INCOMPLETE",
        "exit_code": None,
        "counts": None,
        "biological_validation": False,
    }
    summary = out / "summary.json"
    summary.write_text(json.dumps(report, indent=2) + "\n")
    xml = out / "results.private.xml"
    code = run_logged(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            f"--junitxml={xml}",
            *EXECUTABLE[args.examination],
        ],
        root,
        out / "results.private.log",
        env,
        args.timeout,
    )
    try:
        counts = junit_counts(xml)
    except (OSError, ET.ParseError):
        counts = None
    unchanged = git(root, "rev-parse", "HEAD") == source and not git(root, "status", "--porcelain")
    status = stage_status(code, counts)
    report.update(
        exit_code=code,
        counts=counts,
        source_unchanged=unchanged,
        overall="PASS" if status == "PASS" and unchanged else "REVIEW_REQUIRED",
    )
    summary.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
