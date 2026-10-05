"""Versioned query rendering and fail-closed identifier audits."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from perturb_lm.sklearn_api.datasets import present


@dataclass(frozen=True)
class QueryPolicy:
    name: str
    version: str
    allowed_fields: tuple[str, ...]
    permits_gene: bool = False
    provisional: bool = False


BASE_FIELDS = ("Metadata_pert_type", "Metadata_control_type", "Metadata_negcon_control_type")
POLICIES = {
    "M0_GENE_AWARE_V1": QueryPolicy("M0_GENE_AWARE_V1", "1", ("Metadata_gene", *BASE_FIELDS), True),
    "M0_IDENTITY_FREE_V2": QueryPolicy("M0_IDENTITY_FREE_V2", "2", BASE_FIELDS),
    "M1_BIOLOGICAL_CONTEXT": QueryPolicy(
        "M1_BIOLOGICAL_CONTEXT", "1-draft", ("biological_context",), provisional=True
    ),
    "M5_LEAKAGE_CONTROL": QueryPolicy("M5_LEAKAGE_CONTROL", "1-draft", (), provisional=True),
}
IDENTIFIER_FIELDS = (
    "treatment",
    "perturbation",
    "compound",
    "record_id",
    "profile_id",
    "image_id",
    "sample_id",
    "batch",
    "source",
    "plate",
    "well",
    "replicate",
    "source_profile_file",
    "source_profile_row",
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_pert_id",
    "Metadata_target_sequence",
    "Metadata_smiles",
    "Metadata_InChIKey",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Batch",
    "Metadata_Inferred_Batch",
    "gene",
    "Metadata_gene",
    "gene_aliases",
)


def _normalize(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value)).casefold()


def audit_text(text: str, policy: QueryPolicy, universe: pd.DataFrame) -> dict:
    """Audit against the entire supplied identifier universe, including short symbols.

    Token boundaries avoid treating a one-letter identifier as every occurrence of that
    letter. Punctuation-containing identifiers are escaped literally. Aliases must be
    supplied explicitly; this is not an external biological entity recognizer.
    """
    violations = []
    checked = 0
    for field in IDENTIFIER_FIELDS:
        if field not in universe or (
            policy.permits_gene and field in {"gene", "Metadata_gene", "gene_aliases"}
        ):
            continue
        for value in universe[field]:
            values = value if isinstance(value, (tuple, list)) else [value]
            for identifier in values:
                if not present(identifier):
                    continue
                checked += 1
                pattern = r"(?<!\w)" + re.escape(_normalize(identifier)) + r"(?!\w)"
                if re.search(pattern, _normalize(text)):
                    violations.append(field)
    if violations:
        raise ValueError(
            f"Prohibited identifier in rendered text; fields={sorted(set(violations))}"
        )
    return {
        "passed": True,
        "checked_values": checked,
        "violations": [],
        "scope": "supplied_identifier_universe",
        "audit_version": "1",
    }


class QueryPolicyTransformer(TransformerMixin, BaseEstimator):
    def __init__(self, policy: str = "M0_IDENTITY_FREE_V2"):
        self.policy = policy

    def fit(self, X: pd.DataFrame, y=None):
        if self.policy not in POLICIES:
            raise ValueError(f"Unknown query policy: {self.policy}")
        self.identifier_universe_ = X.copy()
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        check_is_fitted(self, "identifier_universe_")
        policy = POLICIES[self.policy]
        universe = pd.concat([self.identifier_universe_, X], ignore_index=True)
        rows = []
        for _, row in X.iterrows():
            if not present(row.get("record_id")):
                raise ValueError("Queries require record_id; relevance is validated separately")
            parts = [
                str(row[f]).strip() for f in policy.allowed_fields if f in row and present(row[f])
            ]
            if self.policy == "M0_GENE_AWARE_V1":
                gene = row.get("Metadata_gene")
                pert_type = row.get("Metadata_pert_type")
                pert_type = pert_type if present(pert_type) else "unknown"
                text = (
                    f"cells with perturbation of {gene}"
                    if present(gene)
                    else f"cells with perturbation type {pert_type}"
                )
            elif self.policy == "M1_BIOLOGICAL_CONTEXT" and not parts:
                raise ValueError(
                    "M1 requires supplied biological_context and annotation provenance"
                )
            else:
                text = " ".join(dict.fromkeys(parts)) or "cellular perturbation"
            if self.policy == "M1_BIOLOGICAL_CONTEXT" and not present(
                row.get("annotation_provenance")
            ):
                raise ValueError("M1 requires annotation_provenance")
            audit = audit_text(text, policy, universe)
            key = json.dumps(
                [row.get("dataset", ""), row["record_id"], policy.name, policy.version]
            )
            result = row.to_dict()
            result.update(
                query_id=hashlib.sha256(key.encode()).hexdigest()[:24],
                policy_name=policy.name,
                policy_version=policy.version,
                allowed_source_fields=policy.allowed_fields,
                rendered_text=text,
                biological_identity={
                    k: row.get(k, "") for k in ("treatment", "gene", "compound", "perturbation")
                },
                provenance={
                    "record_id": row["record_id"],
                    "annotation": row.get("annotation_provenance", ""),
                },
                leakage_audit=audit,
            )
            rows.append(result)
        result = pd.DataFrame(rows)
        if result.empty or result.query_id.duplicated().any():
            raise ValueError("Query IDs must be unique and nonempty")
        return result
