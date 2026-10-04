"""Explicit train/test separation and candidate-level exclusion reasons."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from perturb_lm.sklearn_api.datasets import present

SPLIT_FIELDS = {
    "held_out_plate": ("dataset", "source", "batch", "plate"),
    "held_out_treatment": ("treatment",),
    "held_out_batch": ("dataset", "batch"),
    "leave_one_source_out": ("source",),
    "cross_dataset_transfer": ("dataset",),
}
FILTER_FIELDS = {
    "same_plate": ("dataset", "source", "batch", "plate"),
    "same_well_coordinate": ("well",),
    "same_treatment": ("treatment",),
    "same_batch": ("dataset", "batch"),
    "same_source": ("source",),
}


@dataclass(frozen=True)
class SplitSpec:
    kind: str = "held_out_plate"
    exclude: tuple[str, ...] = ("same_plate", "same_well_coordinate")

    def __post_init__(self):
        if self.kind not in {*SPLIT_FIELDS, "unfiltered"}:
            raise ValueError(f"Unsupported split: {self.kind}")
        if set(self.exclude) - set(FILTER_FIELDS):
            raise ValueError("Unsupported leakage filter")
        if len(set(self.exclude)) != len(self.exclude):
            raise ValueError("Duplicate leakage filters")

    def validate(self, train: pd.DataFrame, test: pd.DataFrame) -> None:
        if self.kind == "unfiltered":
            raise ValueError("Unfiltered is evaluation-only; training requires a held-out split")
        fields = SPLIT_FIELDS[self.kind]
        for frame in (train, test):
            if frame.empty:
                raise ValueError("Split requires nonempty train and test partitions")
            if any(f not in frame or not frame[f].map(present).all() for f in fields):
                raise ValueError(f"Split requires nonmissing fields: {fields}")
        train_keys = set(train.loc[:, list(fields)].itertuples(index=False, name=None))
        test_keys = set(test.loc[:, list(fields)].itertuples(index=False, name=None))
        if train_keys & test_keys:
            raise ValueError(f"Train/test leakage in {self.kind}")
        if (
            "record_id" in train
            and "record_id" in test
            and set(train.record_id) & set(test.record_id)
        ):
            raise ValueError("Train/test record identity leakage")


def candidate_exclusions(
    query: pd.Series,
    candidates: pd.DataFrame,
    spec: SplitSpec,
    required_field: str | None = "treatment",
) -> list[tuple[str, ...]]:
    from perturb_lm.sklearn_api.contracts import canonical_well

    reasons = []
    for _, candidate in candidates.iterrows():
        row_reasons = []
        if query.get("record_id") == candidate.get("record_id"):
            row_reasons.append("same_record")
        if required_field is not None and not present(candidate.get(required_field)):
            row_reasons.append(f"missing_candidate_{required_field}")
        for rule in spec.exclude:
            fields = FILTER_FIELDS[rule]
            if any(not present(query.get(f)) or not present(candidate.get(f)) for f in fields):
                row_reasons.append(f"missing_metadata:{rule}")
            elif all(
                canonical_well(query[f]) == canonical_well(candidate[f])
                if f == "well"
                else query[f] == candidate[f]
                for f in fields
            ):
                row_reasons.append(rule)
        reasons.append(tuple(row_reasons))
    return reasons
