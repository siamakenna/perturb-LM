"""Count query information using the unchanged production renderers (#52, #30)."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

from perturb_lm.audits.cohort import clean
from perturb_lm.retrieval.text_profile import build_metadata_text_queries
from perturb_lm.sklearn_api.queries import (
    BASE_FIELDS,
    IDENTIFIER_FIELDS,
    POLICIES,
    QueryPolicyTransformer,
    audit_text,
)


def compact_universe(frame: pd.DataFrame) -> pd.DataFrame:
    """Column-wise deduplication preserves all identifiers; rendering uses no associations."""
    return pd.DataFrame(
        {
            c: pd.Series(sorted(set(frame[c].map(clean)) - {""}))
            for c in IDENTIFIER_FIELDS
            if c in frame
        }
    ).fillna("")


def render_queries(frame: pd.DataFrame, policy: str) -> pd.DataFrame:
    """Render distinct allowed-field signatures through the real transformer, then expand.

    Rendering uses allowed fields only. A separate full-universe scan records blocked
    text without weakening the production gate. These counts are not runnable queries.
    """
    if frame.record_id.eq("").any() or frame.record_id.duplicated().any():
        raise ValueError("Unique nonempty record IDs required")
    work = frame.copy()
    fields = list(POLICIES[policy].allowed_fields)
    for field in fields:
        work[field] = work[field].map(clean) if field in work else ""
    unique = work.drop_duplicates(fields).copy()
    render_input = unique[["record_id", *fields]]
    transformed = QueryPolicyTransformer(policy).fit(render_input).transform(render_input)
    lookup = transformed[fields + ["rendered_text"]]
    result = work.merge(lookup, on=fields, how="left", validate="many_to_one", sort=False)
    universe = compact_universe(work)
    violations = scan_identifiers(result.rendered_text.unique(), policy, universe)
    result["blocked_fields"] = result.rendered_text.map(violations)
    return result


def scan_identifiers(texts, policy: str, universe: pd.DataFrame) -> dict[str, str]:
    """Batch equivalent of production's literal token-boundary dictionary check.

    Suspected matches are confirmed by the unchanged production audit. No external
    alias recognition is claimed. Compiling per field avoids redundant per-row scans.
    """
    rules = {}
    for field in IDENTIFIER_FIELDS:
        if field not in universe or (
            POLICIES[policy].permits_gene and field in {"gene", "Metadata_gene", "gene_aliases"}
        ):
            continue
        values = sorted(set(universe[field].map(clean)) - {"", "none"})
        if values:
            literals = [re.escape(unicodedata.normalize("NFKC", v).casefold()) for v in values]
            rules[field] = re.compile(r"(?<!\w)(?:" + "|".join(literals) + r")(?!\w)")
    result = {}
    for text in texts:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        fields = sorted(field for field, pattern in rules.items() if pattern.search(normalized))
        if fields:
            try:
                audit_text(text, POLICIES[policy], universe)
            except ValueError:
                pass
            else:
                raise AssertionError("Batch scan disagrees with production audit")
        result[text] = "|".join(fields)
    return result


def query_counts(frame: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Collisions mean distinct supplied treatment IDs, not proof of distinct phenotypes."""
    groups = []
    for text, group in frame.groupby("rendered_text", sort=True):
        treatments = set(group.treatment.map(clean)) - {"", "none"}
        groups.append(
            {
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "query_count": len(group),
                "distinct_treatments": len(treatments),
                "missing_treatment_queries": int(group.treatment.map(clean).eq("").sum()),
                "collision": len(treatments) > 1,
            }
        )
    table = pd.DataFrame(groups)
    collided = table[table.collision] if len(table) else table
    n = len(frame)
    stats = {
        "total_queries": n,
        "unique_strings": len(table),
        "collision_groups": len(collided),
        "queries_in_collisions": int(collided.query_count.sum()) if len(table) else 0,
        "missing_treatment_queries": int(frame.treatment.map(clean).eq("").sum()),
        "collision_fraction": float(collided.query_count.sum() / n) if n else None,
    }
    return stats, table


def audit_queries(profiles: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    frame = profiles.copy()
    if "Metadata_broad_sample" not in frame:
        raise ValueError("Treatment metadata column required; missing values may be blank")
    for field in ("Metadata_gene", *BASE_FIELDS):
        if field not in frame:
            frame[field] = ""
    frame["treatment"] = frame.Metadata_broad_sample.map(clean)
    frame["dataset"] = "CPJUMP1"
    for alias, field in (
        ("plate", "Metadata_Plate"),
        ("well", "Metadata_Well"),
        ("batch", "path_batch"),
        ("gene", "Metadata_gene"),
    ):
        frame[alias] = frame[field] if field in frame else ""
    labeled = frame[frame.treatment.ne("")]
    historical = build_metadata_text_queries(frame, label_column="Metadata_broad_sample")
    historical = historical.rename(
        columns={"mechanism_query_text": "rendered_text", "target_label": "treatment"}
    )
    result = {"historical_treatment_level_gene_aware": query_counts(historical)[0]}
    groups = []
    for policy in ("M0_GENE_AWARE_V1", "M0_IDENTITY_FREE_V2"):
        rendered = render_queries(frame, policy)
        stats, table = query_counts(rendered)
        labeled_rendered = rendered[rendered.treatment.ne("")]
        stats["labeled_population"] = query_counts(labeled_rendered)[0]
        # Reproduce first-record-per-treatment selection explicitly; report separately.
        treatment_rows = labeled_rendered.drop_duplicates("treatment")
        stats["first_record_per_treatment"] = query_counts(treatment_rows)[0]
        stats["treatments_with_multiple_renderings"] = int(
            labeled_rendered.groupby("treatment").rendered_text.nunique().gt(1).sum()
        )
        generic = (
            rendered.Metadata_gene.map(clean).eq("")
            if policy.endswith("V1")
            else pd.Series(True, index=rendered.index)
        )
        stats["queries_with_only_generic_category_content"] = int(generic.sum())
        stats["generic_category_fraction"] = float(generic.mean())
        stats["gene_present_queries"] = int(rendered.Metadata_gene.map(clean).ne("").sum())
        stats["prohibited_identifier_blocked_queries"] = int(rendered.blocked_fields.ne("").sum())
        stats["blocked_text_groups"] = int(
            rendered.loc[rendered.blocked_fields.ne(""), "rendered_text"].nunique()
        )
        stats["blocked_field_counts"] = {
            field: int(
                rendered.blocked_fields.str.split("|").map(lambda x, field=field: field in x).sum()
            )
            for field in IDENTIFIER_FIELDS
            if rendered.blocked_fields.str.split("|").map(lambda x, field=field: field in x).any()
        }
        stats["prohibited_identifier_audit"] = (
            "blocked"
            if stats["prohibited_identifier_blocked_queries"]
            else "passed: supplied identifier universe only"
        )
        stats["all_allowed_fields_missing_queries"] = int(
            rendered[list(POLICIES[policy].allowed_fields)].eq("").all(axis=1).sum()
        )
        category_cols = [c for c in BASE_FIELDS if c in rendered]
        stats["category_signature_count"] = len(rendered[category_cols].drop_duplicates())
        stats["text_variation_within_category_signatures"] = int(
            rendered.groupby(category_cols, dropna=False).rendered_text.nunique().gt(1).sum()
        )
        if policy.endswith("V1"):
            first = treatment_rows.set_index("treatment").rendered_text.sort_index()
            old = historical.set_index("treatment").rendered_text.sort_index()
            stats["matches_historical_treatment_renderer"] = first.equals(old)
        result[policy] = stats
        table["policy"] = policy
        groups.append(table)
    result["labeled_rows"] = len(labeled)
    result["limitations"] = (
        "Dictionary-based leakage audit only; unprovided aliases and implicit biological "
        "identity are not certified absent. Category content is an operational definition "
        "of weak information, not an ontology-derived biological information score."
    )
    return result, pd.concat(groups, ignore_index=True)
