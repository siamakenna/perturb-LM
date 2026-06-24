from __future__ import annotations

import numpy as np
import pandas as pd
from PIL import Image

from perturb_lm.images.composite import render_manifest_composites, render_rgb_composite


def test_render_rgb_composite_from_channel_images(tmp_path) -> None:
    ch1 = tmp_path / "ch1.png"
    ch2 = tmp_path / "ch2.png"
    Image.fromarray(np.full((8, 8), 10, dtype=np.uint8)).save(ch1)
    Image.fromarray(np.full((8, 8), 200, dtype=np.uint8)).save(ch2)

    image = render_rgb_composite(
        {
            "image_path_ch1": ch1,
            "image_path_ch2": ch2,
        },
        output_size=(4, 4),
    )

    assert image.mode == "RGB"
    assert image.size == (4, 4)


def test_render_manifest_composites_reports_missing_and_rendered_rows(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    Image.fromarray(np.arange(64, dtype=np.uint8).reshape(8, 8)).save(raw_root / "site_ch1.png")
    manifest = pd.DataFrame(
        [
            {
                "dataset": "rxrx1",
                "site_id": "site/1",
                "experiment": "exp1",
                "plate": "plate1",
                "well": "A01",
                "site": "1",
                "perturbation_id": "sirna1",
                "perturbation_name": "GENE1",
                "image_path_ch1": "site_ch1.png",
            },
            {
                "dataset": "rxrx1",
                "site_id": "site/2",
                "experiment": "exp1",
                "plate": "plate1",
                "well": "A02",
                "site": "1",
                "perturbation_id": "sirna2",
                "perturbation_name": "GENE2",
                "image_path_ch1": "missing.png",
            },
        ]
    )

    composites = render_manifest_composites(
        manifest,
        tmp_path / "composites",
        raw_root=raw_root,
        output_size=(4, 4),
    )

    assert composites["composite_status"].tolist() == ["rendered", "missing_channels"]
    assert (tmp_path / "composites" / "site_1.png").exists()
