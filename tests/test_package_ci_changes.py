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
        {"action": "synchronize", "before": 2},
    ):
        assert changes.comparison(event) is None


def test_opened_event_requests_rebuild_without_path_environment(monkeypatch, capsys):
    monkeypatch.setenv("PACKAGE_EVENT_ACTION", "opened")
    monkeypatch.delenv("PACKAGE_EVENT_BEFORE", raising=False)
    changes.main()
    captured = capsys.readouterr()
    assert captured.out == "rebuild=true\n"
    assert captured.err == "Artifact rebuild required\n"


def test_valid_synchronize_event_can_reuse_bookkeeping_evidence(monkeypatch, capsys):
    class Result:
        returncode = 0
        stdout = b"scripts/package_ci_changes.py\0"

    monkeypatch.setenv("PACKAGE_EVENT_ACTION", "synchronize")
    monkeypatch.setenv("PACKAGE_EVENT_BEFORE", "a" * 40)
    monkeypatch.setattr(changes.subprocess, "run", lambda *args, **kwargs: Result())
    changes.main()
    captured = capsys.readouterr()
    assert captured.out == "rebuild=false\n"
    assert "Bookkeeping-only update" in captured.err


def test_invalid_before_never_reaches_git(monkeypatch, capsys):
    def deny(*args, **kwargs):
        raise AssertionError("invalid comparison must not reach git")

    monkeypatch.setenv("PACKAGE_EVENT_ACTION", "synchronize")
    monkeypatch.setenv("PACKAGE_EVENT_BEFORE", "not-a-commit")
    monkeypatch.setattr(changes.subprocess, "run", deny)
    changes.main()
    captured = capsys.readouterr()
    assert captured.out == "rebuild=true\n"
