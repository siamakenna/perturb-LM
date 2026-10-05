"""Explicit relevance, population and identity contracts, independent of rendering."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass

import pandas as pd

from perturb_lm.sklearn_api.datasets import present
from perturb_lm.sklearn_api.splits import SplitSpec


@dataclass(frozen=True)
class RelevanceContract:
    name: str
    version: str
    retrieval_unit: str
    positive_rule: str
    identity_fields: tuple[str, ...]
    identity_namespace: str
    query_unit: str = "record"
    candidate_identity: str = "record_id"
    negative_rule: str = "eligible_nonpositive"
    replicate_handling: str = "retain"
    duplicate_handling: str = "reject"
    zero_positive: str = "exclude_and_report"
    normalization: str = "nfkc_strip_exact"
    permitted_metadata: tuple[str, ...] = (
        "Metadata_gene",
        "Metadata_pert_type",
        "Metadata_control_type",
        "Metadata_negcon_control_type",
    )
    exclusions: tuple[str, ...] = ("same_plate", "same_well_coordinate")
    held_out_behavior: str = "validate_before_fit"
    cross_dataset: bool = False
    mapping_provenance: str | None = None
    approval: str = "proposed"
    approval_reference: str | None = None

    def __post_init__(self):
        if not self.name or not self.version or not self.identity_namespace:
            raise ValueError("Contract requires name, version and identity namespace")
        if self.retrieval_unit not in {"treatment", "well", "profile", "image"}:
            raise ValueError("Unknown retrieval unit")
        if self.positive_rule not in {
            "exact_treatment",
            "exact_gene_context",
            "exact_compound_context",
        }:
            raise ValueError("Relevance rule must be explicitly implemented; no inferred biology")
        required = {
            "exact_treatment": {"treatment"},
            "exact_gene_context": {"gene", "perturbation_type", "species"},
            "exact_compound_context": {"compound", "dose", "timepoint"},
        }
        if not required[self.positive_rule] <= set(self.identity_fields):
            raise ValueError("Relevance identity_fields omit required biological context")
        if self.query_unit not in {"record", "identity"}:
            raise ValueError("Query unit must be record or identity")
        if self.query_unit == "identity" and self.exclusions:
            raise ValueError(
                "Identity queries with layout exclusions require an approved anchor rule"
            )
        if self.candidate_identity != "record_id" or self.negative_rule != "eligible_nonpositive":
            raise ValueError("Unsupported candidate identity or negative rule")
        expected = "mean_scores_after_filtering" if self.retrieval_unit == "treatment" else "retain"
        if self.replicate_handling != expected or self.duplicate_handling != "reject":
            raise ValueError(f"This retrieval unit requires replicate_handling={expected}")
        if (
            self.zero_positive != "exclude_and_report"
            or self.held_out_behavior != "validate_before_fit"
        ):
            raise ValueError("Unsupported exclusion or split behavior")
        if self.normalization != "nfkc_strip_exact":
            raise ValueError("Identity normalization must preserve case and leading zeros")
        SplitSpec(exclude=self.exclusions)
        if self.cross_dataset and not self.mapping_provenance:
            raise ValueError(
                "Cross-dataset relevance requires reviewed identity mapping provenance"
            )
        if self.approval not in {"proposed", "synthetic", "approved"}:
            raise ValueError("Unknown scientific approval status")
        if self.approval == "approved" and not self.approval_reference:
            raise ValueError("Approved relevance requires an explicit decision/issue reference")

    @classmethod
    def from_dict(cls, payload):
        payload = dict(payload)
        for key in ("identity_fields", "permitted_metadata", "exclusions"):
            if key in payload:
                payload[key] = tuple(payload[key])
        return cls(**payload)

    def to_dict(self):
        return asdict(self)

    def require_execution(self, synthetic: bool):
        if type(synthetic) is not bool:
            raise ValueError("synthetic must be a boolean")
        if not synthetic and self.approval != "approved":
            raise ValueError("needs_scientific_approval: approve the explicit relevance contract")

    def identity(self, row: pd.Series) -> str | None:
        values = [row.get(key) for key in self.identity_fields]
        if not all(present(value) for value in values):
            return None
        return json.dumps(
            [
                self.identity_namespace,
                *([] if self.cross_dataset else [str(row.get("dataset", ""))]),
                *[unicodedata.normalize("NFKC", str(value)).strip() for value in values],
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.identity_fields) - set(frame)
        if missing:
            raise ValueError(f"Missing relevance fields: {sorted(missing)}")
        result = frame.copy()
        result["relevance_identity"] = result.apply(self.identity, axis=1)
        return result

    def validate_split(self, train, test, split: SplitSpec):
        if tuple(split.exclude) != tuple(self.exclusions):
            raise ValueError("Split filters differ from the relevance contract")
        left, right = self.prepare(train), self.prepare(test)
        if not left.relevance_identity.map(present).all():
            raise ValueError("Training rows require complete relevance identities")
        if split.kind == "held_out_treatment":
            # Hold out the declared identity, even when no treatment column exists.
            split.validate(
                left.assign(treatment=left.relevance_identity),
                right.assign(treatment=right.relevance_identity),
            )
        else:
            split.validate(train, test)
        if split.kind == "cross_dataset_transfer" and not self.cross_dataset:
            raise ValueError("Cross-dataset retrieval requires a compatible relevance contract")
        if split.kind == "held_out_treatment":
            overlap = set(left.relevance_identity.dropna()) & set(right.relevance_identity.dropna())
            if overlap:
                raise ValueError("Held-out identity leakage under the selected relevance rule")


def canonical_well(value: object) -> str:
    """A1/a01/A01 are the same coordinate; never normalize other opaque identifiers."""
    if not present(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().upper()
    match = re.fullmatch(r"([A-Z]+)0*(\d+)", text)
    return f"{match[1]}{int(match[2]):02d}" if match else text


def identity_queries(queries: pd.DataFrame, contract: RelevanceContract) -> pd.DataFrame:
    if contract.query_unit == "record":
        return queries
    rows = []
    for identity, group in queries.groupby("relevance_identity", sort=True, dropna=False):
        if not present(identity):
            rows.extend(group.to_dict("records"))
            continue
        if group.rendered_text.nunique() != 1:
            raise ValueError("Identity queries require consistent rendered text across replicates")
        row = group.sort_values("record_id").iloc[0].copy()
        payload = [identity, row.policy_name, row.policy_version, contract.name, contract.version]
        row["query_id"] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:24]
        row["record_id"] = "identity-query:" + row.query_id
        rows.append(row.to_dict())
    return pd.DataFrame(rows)
