import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "phase4_examinations", ROOT / "scripts/run_phase4_examinations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_uses_existing_synthetic_tests_only(runner):
    payload = runner.manifest(ROOT / "configs/phase4_examinations_v1.json")
    assert len(payload["examinations"]) == 10
    assert len(runner.EXECUTABLE) == 5
    for paths in runner.EXECUTABLE.values():
        for path in paths:
            assert (ROOT / path.split("::")[0]).is_file()


def test_unapproved_examination_rejected_before_execution(runner, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--repo", ".", "--out", "/unused", "--examination", "representations"],
    )
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
