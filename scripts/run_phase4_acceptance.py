#!/usr/bin/env python3
"""Run existing Phase 4 suites; publish counts, never raw logs or test values."""

import argparse
import hashlib
import importlib.metadata as md
import importlib.util
import json
import os
import platform
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

SUITES = {
    "images": [
        "tests/test_pixel_analyzer.py",
        "tests/test_pixel_workflow.py",
        "tests/test_pixel_installed.py",
    ],
    "comparators": ["tests/test_comparator_text_encoders.py"],
    "repository": [],
}


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def junit_counts(path):
    """Count testcase elements, not nested testsuite totals."""
    cases = list(ET.parse(path).getroot().iter("testcase"))
    counts = dict(passed=0, failed=0, errors=0, skipped=0)
    for case in cases:
        key = (
            "errors" if case.find("error") is not None else
            "failed" if case.find("failure") is not None else
            "skipped" if case.find("skipped") is not None else "passed"
        )
        counts[key] += 1
    return dict(total=len(cases), **counts)


def run_logged(command, repo, log, env, timeout):
    with log.open("x", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command, cwd=repo, env=env, stdout=handle,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return process.wait()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return 124


def stage_status(code, counts):
    if code != 0 or not counts or counts["passed"] == 0:
        return "FAIL"
    if counts["failed"] or counts["errors"]:
        return "FAIL"
    return "PASS_WITH_SKIPS" if counts["skipped"] else "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    if platform.system() != "Linux" or sys.version_info < (3, 11):
        parser.error("Use Linux with Python 3.11 or newer.")
    if args.timeout <= 0 or out.is_relative_to(repo) or out.exists():
        parser.error("Use a new output directory outside the checkout and a positive timeout.")
    sha = git(repo, "rev-parse", "HEAD")
    if git(repo, "status", "--porcelain"):
        parser.error("Target checkout must be clean; keep this runner outside it during validation.")
    for filenames in SUITES.values():
        for name in filenames:
            if not (repo / name).is_file():
                parser.error(f"Required test file missing: {name}")
    spec = importlib.util.find_spec("perturb_lm")
    locations = list(spec.submodule_search_locations or []) if spec else []
    if not any(
        Path(location).resolve().is_relative_to(repo / "src") for location in locations
    ):
        parser.error("Install this exact checkout in the selected environment before validation.")
    os.umask(0o077)
    out.mkdir(parents=True)
    env = os.environ.copy()
    for key in ("PYTEST_ADDOPTS", "PYTHONPATH", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env.update(
        OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", MPLBACKEND="Agg",
        HF_HOME=str(out / "empty-model-cache"), PYTHONUNBUFFERED="1",
    )
    versions = {}
    for name in ("perturb-lm", "pytest", "numpy", "scikit-learn", "scikit-image",
                 "scipy", "tifffile", "torch", "transformers", "build"):
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = "not-installed"
    report = {
        "schema_version": 1, "scope": "linux_source_and_installed_pixel_tests",
        "source_commit": sha,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "packages": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages_overlap_do_not_sum_counts": True,
        "github_required_checks_replaced": False,
        "pretrained_model_benchmark_performed": False,
        "overall": "INCOMPLETE", "stages": {},
    }
    summary = out / "summary.json"
    summary.write_text(json.dumps(report, indent=2) + "\n")
    for name, selection in SUITES.items():
        print(f"RUNNING: {name}", flush=True)
        start = time.monotonic()
        xml = out / f"{name}.private.xml"
        command = [sys.executable, "-m", "pytest", "-q", "-ra", "-o", "addopts=",
                   f"--junitxml={xml}", *selection]
        code = run_logged(command, repo, out / f"{name}.private.log", env, args.timeout)
        try:
            counts = junit_counts(xml)
        except (OSError, ET.ParseError):
            counts = None
        status = stage_status(code, counts)
        report["stages"][name] = dict(
            status=status, exit_code=code, counts=counts,
            elapsed_seconds=round(time.monotonic() - start, 2),
        )
        unchanged = (
            git(repo, "rev-parse", "HEAD") == sha
            and not git(repo, "status", "--porcelain")
        )
        report["source_unchanged"] = unchanged
        # Image and comparator groups must not silently skip feature coverage.
        if (
            status == "FAIL"
            or not unchanged
            or (name != "repository" and status != "PASS")
        ):
            report["overall"] = "REVIEW_REQUIRED"
            summary.write_text(json.dumps(report, indent=2) + "\n")
            print(f"STOP: {name}; inspect the private log and summary. No success recorded.")
            return 1
        summary.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{status}: {name}: {counts}", flush=True)
    report["overall"] = report["stages"]["repository"]["status"]
    summary.write_text(json.dumps(report, indent=2) + "\n")
    print("Finished. Review summary.json before sharing; keep *.private.* on approved storage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
