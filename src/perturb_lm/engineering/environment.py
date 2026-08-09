"""Public-safe environment reporting."""

from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

CORE_PACKAGES = [
    "numpy",
    "pandas",
    "pyarrow",
    "pillow",
    "requests",
    "scikit-learn",
    "tqdm",
    "typer",
    "PyYAML",
]
DEV_PACKAGES = ["pytest", "ruff"]
OPTIONAL_MODELING_PACKAGES = ["sentence-transformers"]
PHASE3C_PACKAGES = ["torch", "transformers"]
HUGGING_FACE_CACHE_ENV_VARS = ["HF_HOME", "TRANSFORMERS_CACHE"]
CREDENTIAL_ENV_VARS = ["HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"]


def build_environment_report() -> dict[str, Any]:
    """Build a public-safe report with versions and platform only."""

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "supported_python": ">=3.10",
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "executable_path_included": False,
        "core_dependencies": _package_versions(CORE_PACKAGES),
        "development_dependencies": _package_versions(DEV_PACKAGES),
        "optional_modeling_dependencies": _package_versions(OPTIONAL_MODELING_PACKAGES),
        "phase3c_dependencies": _package_versions(PHASE3C_PACKAGES),
        "heavy_modeling_dependencies_default": False,
        "phase3c_runtime_target": {
            "recommended_default": "Google Colab or another Linux CUDA GPU runtime",
            "acceptable_alternates": [
                "Linux CPU runtime for small or slower frozen-encoder runs",
                "local Windows for dry-run documentation and synthetic tests",
                "managed GPU host when commit, package, device, and cache details are recorded",
            ],
        },
        "hardware": _hardware_report(),
        "device": _device_report(),
        "git": _git_report(),
        "phase3c_storage_policy": {
            "actual_paths_included": False,
            "persistent_storage_location": (
                "/content/drive/... or $PROJECT_ROOT local ignored storage"
            ),
            "data_root": "$PROJECT_ROOT/data/raw/jump_pilot",
            "output_root": "$PROJECT_ROOT/outputs/phase3c",
            "hugging_face_cache_location": (
                "/content/drive/.../cache/huggingface or "
                "$PROJECT_ROOT/.cache/huggingface"
            ),
            "hugging_face_cache_env_vars": HUGGING_FACE_CACHE_ENV_VARS,
            "ignored_roots": ["data/", "outputs/", "results/", "models/", ".cache/"],
        },
        "credential_safety": {
            "credential_values_included": False,
            "credential_env_vars_redacted": CREDENTIAL_ENV_VARS,
            "private_absolute_paths_included": False,
        },
        "ci_install_command": 'python -m pip install -e ".[dev]"',
        "smoke_commands": [
            "python scripts/run_phase1_smoke.py --out outputs/phase1_smoke",
            "python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke",
            (
                "python scripts/run_phase3b_projection_smoke.py "
                "--out outputs/phase3b_projection_smoke --seed 0"
            ),
        ],
    }


def environment_report_json() -> str:
    """Return the environment report as stable JSON."""

    return json.dumps(build_environment_report(), indent=2, sort_keys=True) + "\n"


def _hardware_report() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "system_ram_gb": _system_ram_gb(),
        "hostname_included": False,
    }


def _device_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "torch_import_available": False,
        "cuda_available": None,
        "cuda_version": None,
        "cuda_device_count": None,
        "gpu_name": None,
        "gpu_vram_gb": None,
        "mps_available": None,
        "auto_device_order": ["cuda", "mps", "cpu"],
        "cpu_fallback_supported": True,
        "cpu_fallback_note": (
            "CPU is valid for tests and small dry runs; final embedding and evaluation "
            "runs must record the actual runtime device."
        ),
    }
    if importlib.util.find_spec("torch") is None:
        report["probe_status"] = "torch_not_installed"
        return report
    try:
        import torch
    except Exception as exc:  # pragma: no cover - defensive for broken local installs.
        report["probe_status"] = "torch_import_failed"
        report["probe_error_type"] = type(exc).__name__
        return report

    report["torch_import_available"] = True
    report["probe_status"] = "ok"
    cuda_available = bool(torch.cuda.is_available())
    report["cuda_available"] = cuda_available
    report["cuda_version"] = getattr(torch.version, "cuda", None)
    report["cuda_device_count"] = int(torch.cuda.device_count()) if cuda_available else 0
    if cuda_available:
        report["gpu_name"] = torch.cuda.get_device_name(0)
        properties = torch.cuda.get_device_properties(0)
        report["gpu_vram_gb"] = round(int(properties.total_memory) / (1024**3), 2)
    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None:
        report["mps_available"] = bool(mps_backend.is_available())
    return report


def _git_report() -> dict[str, Any]:
    status = _git_output(["status", "--porcelain"])
    branch = _git_output(["branch", "--show-current"]) or _git_output(
        ["rev-parse", "--abbrev-ref", "HEAD"]
    )
    return {
        "commit": _git_output(["rev-parse", "HEAD"]),
        "branch": branch,
        "dirty": None if status is None else bool(status.strip()),
        "status_paths_included": False,
    }


def _git_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def _system_ram_gb() -> float | None:
    try:
        if platform.system() == "Windows":
            return _windows_ram_gb()
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(int(pages) * int(page_size) / (1024**3), 2)
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return None


def _windows_ram_gb() -> float | None:
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(int(status.ullTotalPhys) / (1024**3), 2)


def _package_versions(names: list[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions
