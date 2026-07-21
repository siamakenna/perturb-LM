from __future__ import annotations

import json
import subprocess
import sys

from perturb_lm.engineering.environment import build_environment_report


def test_environment_report_is_public_safe_and_structured() -> None:
    report = build_environment_report()
    text = json.dumps(report)

    assert report["supported_python"] == ">=3.10"
    assert report["executable_path_included"] is False
    assert "numpy" in report["core_dependencies"]
    assert "pytest" in report["development_dependencies"]
    assert "sentence-transformers" in report["optional_modeling_dependencies"]
    assert "/Users/" not in text
    assert ".venv" not in text


def test_print_environment_report_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/print_environment_report.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["heavy_modeling_dependencies_default"] is False
