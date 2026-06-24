from __future__ import annotations

import numpy as np
import pandas as pd
from PIL import Image

from perturb_lm.data.inventory import audit_local_dataset
from perturb_lm.data.rxrx_common import find_metadata_files


def test_audit_local_dataset_reports_metadata_embeddings_and_manifest_images(tmp_path) -> None:
    data_root = tmp_path / "raw"
    rxrx1 = data_root / "rxrx1"
    rxrx1.mkdir(parents=True)
    (rxrx1 / "metadata.csv").write_text("experiment,plate,well,sirna_id\nexp1,p1,A01,s1\n")
    pd.DataFrame({"site_id": ["site1"], "emb_0": [1.0], "emb_1": [0.0]}).to_csv(
        rxrx1 / "embeddings.csv",
        index=False,
    )
    Image.fromarray(np.ones((4, 4), dtype=np.uint8)).save(rxrx1 / "image.png")
    manifest = pd.DataFrame({"image_path_ch1": ["rxrx1/image.png"], "image_path_ch2": ["rxrx1/missing.png"]})

    inventory = audit_local_dataset("rxrx1", data_root, site_manifest=manifest)

    assert inventory.metadata_files == [str(rxrx1 / "metadata.csv")]
    assert inventory.embedding_files == [str(rxrx1 / "embeddings.csv")]
    assert inventory.image_file_counts[".png"] == 1
    assert inventory.manifest_image_paths_checked == 2
    assert inventory.manifest_image_paths_found == 1
    assert inventory.manifest_image_paths_missing == 1


def test_rxrx_metadata_discovery_ignores_unrelated_dataset_metadata(tmp_path) -> None:
    jump_metadata = tmp_path / "raw" / "jump_pilot" / "metadata"
    jump_metadata.mkdir(parents=True)
    (jump_metadata / "experiment-metadata.tsv").write_text("Metadata_Source\nJUMP\n")

    assert find_metadata_files("rxrx1", tmp_path / "raw") == []
