"""Fixed-prediction query versus treatment estimands with keyed paired resampling."""

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone

from perturb_lm.sklearn_api import QueryBootstrap


def frames():
    values = pd.DataFrame(
        {
            "query_id": ["a", "b", "c", "d", "excluded-query"],
            "treatment": ["T1", "T1", "T1", "T2", "T3"],
            "average_precision": [1.0, 1.0, 1.0, 0.0, np.nan],
            "evaluable": [True, True, True, True, False],
        }
    )
    return values, values.assign(average_precision=[0.0, 0.0, 0.0, 0.0, 0.0]).iloc[::-1]


@pytest.mark.parametrize("unit", ["query", "treatment_cluster"])
@pytest.mark.parametrize("estimand,expected", [("query_weighted", 0.75), ("equal_treatment", 0.5)])
def test_pairing_estimands_counts_and_row_order(unit, estimand, expected):
    values, reference = frames()
    model = QueryBootstrap(300, random_state=42, resampling_unit=unit, estimand=estimand)
    result = model.evaluate(values, reference)
    assert result == clone(model).evaluate(values.iloc[::-1], reference.iloc[::-1])
    assert result["estimate"] == expected
    assert result["n_queries"] == 5 and result["n_excluded_queries"] == 1
    assert result["n_treatments"] == 3 and result["n_evaluable_treatments"] == 2
    assert result["uncertainty_scope"] == "fixed_predictions"


def test_whole_treatment_resampling_differs_from_within_treatment_queries():
    values, reference = frames()
    clustered = QueryBootstrap(
        500, random_state=3, resampling_unit="treatment_cluster", estimand="equal_treatment"
    ).evaluate(values, reference)
    within = QueryBootstrap(500, random_state=3, estimand="equal_treatment").evaluate(
        values, reference
    )
    assert (clustered["ci_low"], clustered["ci_high"]) == (0.0, 1.0)
    assert (within["ci_low"], within["ci_high"]) == (0.5, 0.5)


@pytest.mark.parametrize("mutation", ["missing", "mismatch", "duplicate", "population", "sentinel"])
def test_invalid_pairing_fails(mutation):
    values, reference = frames()
    if mutation == "missing":
        reference = reference.drop(columns="treatment")
    elif mutation == "mismatch":
        reference.loc[0, "treatment"] = "other"
    elif mutation == "duplicate":
        reference = pd.concat([reference, reference.iloc[:1]])
    elif mutation == "sentinel":
        reference.loc[0, "treatment"] = "None"
    else:
        reference = reference.iloc[:-1]
    with pytest.raises(ValueError):
        QueryBootstrap(resampling_unit="treatment_cluster").evaluate(values, reference)


def test_single_evaluable_cluster_and_all_nonevaluable_fail():
    values, _ = frames()
    with pytest.raises(ValueError, match="two evaluable treatments"):
        QueryBootstrap(resampling_unit="treatment_cluster").evaluate(values.iloc[:3])
    with pytest.raises(ValueError, match="No evaluable"):
        QueryBootstrap().evaluate(values.assign(evaluable=False))
