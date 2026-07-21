from __future__ import annotations

import pandas as pd

from perturb_lm.modeling.integrity import (
    split_public_checksum,
    validate_query_text_no_identifier_leakage,
    validate_split_integrity,
)


def _split_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "split": ["train", "train", "test", "test"],
            "profile_id": ["p1", "p2", "p3", "p4"],
            "plate": ["plate-a", "plate-b", "plate-c", "plate-c"],
            "well": ["A01", "A02", "B01", "B02"],
            "batch": ["batch-a", "batch-a", "batch-a", "batch-a"],
            "treatment": ["drug-a", "drug-b", "drug-c", "drug-d"],
        }
    )


def test_held_out_plate_integrity_and_public_checksum_are_deterministic() -> None:
    frame = _split_frame()

    report_a = validate_split_integrity(
        frame,
        split_type="held_out_plate",
        n_evaluable_queries=2,
        min_evaluable_queries=1,
    )
    report_b = validate_split_integrity(
        frame,
        split_type="held_out_plate",
        n_evaluable_queries=2,
        min_evaluable_queries=1,
    )

    assert report_a.ok
    assert report_a.checksum == report_b.checksum
    checksum_a = split_public_checksum(frame, group_columns=["plate", "treatment"])
    checksum_b = split_public_checksum(frame, group_columns=["plate", "treatment"])
    assert checksum_a == checksum_b


def test_held_out_treatment_zero_overlap_is_valid_by_design() -> None:
    report = validate_split_integrity(
        _split_frame(),
        split_type="held_out_treatment",
        n_evaluable_queries=2,
    )

    assert report.ok


def test_split_integrity_detects_profile_and_row_overlap() -> None:
    frame = _split_frame()
    frame.loc[2, "profile_id"] = "p1"
    frame.loc[2, ["plate", "well", "batch", "treatment"]] = frame.loc[
        0,
        ["plate", "well", "batch", "treatment"],
    ].to_numpy()

    report = validate_split_integrity(
        frame,
        split_type="held_out_plate",
        n_evaluable_queries=2,
    )

    assert not report.ok
    assert "Train and test profile IDs overlap." in report.errors
    assert "Train and test rows overlap." in report.errors
    assert "Train and test held-out plate values overlap." in report.errors


def test_one_batch_split_warns_instead_of_fabricating_evaluation() -> None:
    report = validate_split_integrity(
        _split_frame(),
        split_type="held_out_batch",
        n_evaluable_queries=2,
    )

    assert report.ok
    assert any("fewer than two batches" in warning for warning in report.warnings)


def test_non_evaluable_queries_fail_when_below_threshold_and_are_not_silent() -> None:
    report = validate_split_integrity(
        _split_frame(),
        split_type="held_out_treatment",
        n_evaluable_queries=0,
        min_evaluable_queries=1,
    )

    assert not report.ok
    assert any("n_evaluable_queries is below" in error for error in report.errors)


def test_unreported_evaluable_query_count_warns_explicitly() -> None:
    report = validate_split_integrity(_split_frame(), split_type="held_out_treatment")

    assert report.ok
    assert any("n_evaluable_queries was not provided" in warning for warning in report.warnings)


def test_query_text_identifier_leakage_detects_plate_well_batch_and_treatment_values() -> None:
    queries = pd.DataFrame(
        {
            "query_text": ["cells treated like plate-a"],
            "plate": ["plate-a"],
            "well": ["A01"],
            "batch": ["batch-a"],
            "treatment": ["drug-c"],
        }
    )

    report = validate_query_text_no_identifier_leakage(
        queries,
        prohibited_columns=["plate", "well", "batch", "treatment"],
    )

    assert not report.ok
    assert "Query text contains a prohibited identifier value." in report.errors


def test_retrieval_filter_split_types_warn_but_do_not_require_treatment_overlap() -> None:
    report = validate_split_integrity(
        _split_frame(),
        split_type="exclude_same_plate_and_well",
        n_evaluable_queries=2,
    )

    assert report.ok
    assert any("retrieval filter" in warning for warning in report.warnings)
