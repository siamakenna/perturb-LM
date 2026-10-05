"""Unit tests for acceptance evidence handling; no model or dataset access."""

import runpy
from pathlib import Path

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "run_phase4_acceptance.py")
)


def test_junit_nested_totals_are_not_double_counted(tmp_path):
    path = tmp_path / "result.xml"
    path.write_text(
        '<testsuites tests="4"><testsuite tests="4">'
        '<testcase name="p"/>'
        '<testcase name="f"><failure message="private text"/></testcase>'
        '<testcase name="e"><error message="private text"/></testcase>'
        '<testcase name="s"><skipped message="private text"/></testcase>'
        '</testsuite></testsuites>'
    )
    assert MODULE["junit_counts"](path) == dict(
        total=4, passed=1, failed=1, errors=1, skipped=1
    )


@pytest.mark.parametrize(
    ("code", "passed", "failed", "errors", "skipped", "expected"),
    [
        (0, 3, 0, 0, 0, "PASS"),
        (0, 3, 0, 0, 1, "PASS_WITH_SKIPS"),
        (1, 3, 1, 0, 0, "FAIL"),
        (2, 0, 0, 1, 0, "FAIL"),
        (5, 0, 0, 0, 0, "FAIL"),
        (0, 0, 0, 0, 2, "FAIL"),
        (124, 2, 0, 0, 0, "FAIL"),
        (0, 3, 1, 0, 0, "FAIL"),
    ],
)
def test_stage_status(code, passed, failed, errors, skipped, expected):
    counts = dict(passed=passed, failed=failed, errors=errors, skipped=skipped)
    assert MODULE["stage_status"](code, counts) == expected


def test_missing_report_is_not_a_pass():
    assert MODULE["stage_status"](0, None) == "FAIL"
