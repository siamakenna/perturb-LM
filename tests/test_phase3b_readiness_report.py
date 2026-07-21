from __future__ import annotations

from pathlib import Path


def test_phase3b_readiness_does_not_reuse_global_baseline_count_for_splits() -> None:
    text = Path("docs/PHASE3B_FOUNDATION_READINESS.md").read_text()
    split_section = text.split("## Split Thresholds", maxsplit=1)[1].split(
        "## Added Guardrails",
        maxsplit=1,
    )[0]

    assert (
        "641 total/evaluable query count applies to the corrected full-query lexical baseline"
        in split_section
    )
    assert "pass with 641 evaluable queries" not in split_section

    split_rows = [
        line
        for line in split_section.splitlines()
        if line.startswith("| ")
        and not line.startswith("| ---")
        and not line.startswith("| Split or filter")
    ]
    requested_rows = [
        row
        for row in split_rows
        if any(
            label in row
            for label in [
                "held-out plate",
                "held-out treatment",
                "held-out well",
                "exclude same plate",
                "exclude same well",
                "exclude same plate and well",
            ]
        )
    ]

    assert len(requested_rows) == 6
    assert all("pending" in row for row in requested_rows)
    assert not all("641" in row for row in requested_rows)
