from __future__ import annotations

import pandas as pd
import pytest

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.schemas import SITE_MANIFEST_COLUMNS, validate_site_manifest


def test_site_manifest_validation_reports_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        validate_site_manifest(pd.DataFrame({"dataset": ["rxrx1"]}))


def test_build_rxrx_manifests_from_fixture(tmp_path) -> None:
    site, perturbations = build_manifests("rxrx1", data_root="tests/fixtures", out_dir=tmp_path)

    assert list(site.columns) == SITE_MANIFEST_COLUMNS
    assert len(site) == 3
    assert len(perturbations) == 2
    assert (tmp_path / "rxrx1_site_manifest.csv").exists()
    assert (tmp_path / "rxrx1_site_manifest.parquet").exists()
    assert (tmp_path / "rxrx1_perturbation_manifest.csv").exists()
    assert (tmp_path / "rxrx1_perturbation_manifest.parquet").exists()
