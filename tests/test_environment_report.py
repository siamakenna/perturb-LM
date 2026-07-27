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
    assert "C:\\Users" not in text
    assert ".venv" not in text


def test_environment_report_records_phase3c_runtime_fields_without_heavy_requirements() -> None:
    report = build_environment_report()

    assert "torch" in report["phase3c_dependencies"]
    assert "transformers" in report["phase3c_dependencies"]
    assert report["phase3c_runtime_target"]["recommended_default"].startswith("Google Colab")
    assert report["hardware"]["hostname_included"] is False
    assert "system_ram_gb" in report["hardware"]
    assert report["device"]["cpu_fallback_supported"] is True
    assert "cuda_available" in report["device"]
    assert "cuda_version" in report["device"]
    assert "gpu_name" in report["device"]
    assert "gpu_vram_gb" in report["device"]
    assert "commit" in report["git"]
    assert "branch" in report["git"]
    assert "dirty" in report["git"]
    assert report["git"]["status_paths_included"] is False
    assert report["phase3c_storage_policy"]["actual_paths_included"] is False
    assert report["credential_safety"]["credential_values_included"] is False


def test_environment_report_does_not_include_credential_values(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "FAKE_TEST_TOKEN_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("HUGGINGFACE_HUB_TOKEN", "FAKE_HUB_TOKEN_SHOULD_NOT_APPEAR")

    text = json.dumps(build_environment_report()).lower()

    assert "fake_test_token_should_not_appear" not in text
    assert "fake_hub_token_should_not_appear" not in text


def test_print_environment_report_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/print_environment_report.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["heavy_modeling_dependencies_default"] is False
