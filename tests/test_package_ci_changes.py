import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "package_changes", Path(__file__).resolve().parents[1] / "scripts/package_ci_changes.py"
)
changes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changes)


@pytest.mark.parametrize(
    "path",
    [
        "src/perturb_lm/_version.py",
        "pyproject.toml",
        "MANIFEST.in",
        "LICENSE",
        "tests/test_release_contract.py",
        "docs/PACKAGE_API.md",
        "docs/PIXEL_PACKAGE_EXAMPLE.md",
        "configs/package-minimum.txt",
        "new_unknown_file",
    ],
)
def test_application_or_unknown_changes_require_build(path):
    assert changes.needs_build([path, ".github/workflows/package.yml"])


def test_only_bookkeeping_can_reuse_existing_evidence():
    assert not changes.needs_build(list(changes.BOOKKEEPING))
    assert not changes.needs_build([])


def test_only_valid_synchronize_sha_can_skip_build():
    assert changes.comparison({"action": "synchronize", "before": "a" * 40}) == "a" * 40
    for event in (
        {},
        {"action": "synchronize", "before": "pending"},
        {"action": "opened", "before": "a" * 40},
    ):
        assert changes.comparison(event) is None
