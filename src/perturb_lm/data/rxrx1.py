"""RxRx1 dataset hooks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from perturb_lm.data.rxrx_common import load_rxrx_metadata, standardize_site_manifest

DATASET = "rxrx1"


def load_metadata(data_root: Path) -> pd.DataFrame:
    return load_rxrx_metadata(DATASET, data_root)


def build_site_manifest(data_root: Path) -> pd.DataFrame:
    return standardize_site_manifest(DATASET, load_metadata(data_root))
