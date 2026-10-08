import importlib.util
import json
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
        {"action": "synchronize", "before": 2},
    ):
        assert changes.comparison(event) is None


def test_output_and_event_paths_must_live_under_runner_temp(tmp_path, monkeypatch):
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir()
    event_path = runner_temp / "event.json"
    event_path.write_text(json.dumps({"action": "opened"}))
    output_path = runner_temp / "output.txt"
    output_path.touch()
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    changes.main()
    assert output_path.read_text() == "rebuild=true\n"

    unauthorized = tmp_path / "output_outside.txt"
    unauthorized.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(unauthorized))
    with pytest.raises(ValueError, match="outside trusted runner temp"):
        changes.main()
    assert unauthorized.read_text() == ""


def test_invalid_file_command_path_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "missing.txt"))
    with pytest.raises(ValueError, match="regular file"):
        changes.safe_env_path("GITHUB_OUTPUT", tmp_path)
