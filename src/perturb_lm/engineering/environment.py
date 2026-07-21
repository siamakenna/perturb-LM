"""Public-safe environment reporting."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import platform
from typing import Any

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
        "heavy_modeling_dependencies_default": False,
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


def _package_versions(names: list[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions
