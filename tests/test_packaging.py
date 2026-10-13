"""Source/bundled contract parity; installed contracts are tested separately."""

from importlib.resources import files
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", ["model_assets", "relevance_contracts"])
def test_bundled_policies_match_reviewed_source(name):
    root = Path(__file__).resolve().parents[1]
    assert (
        files("perturb_lm.resources").joinpath(f"{name}.yaml").read_bytes()
        == (root / "configs/benchmark_v2" / f"{name}.yaml").read_bytes()
    )
