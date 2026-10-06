"""Exercise the real pilot command with the existing tiny offline model fixtures."""

import json
import os
import subprocess
import sys
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest
from test_offline_model_inference import assets, offline  # noqa: F401
from tifffile import imwrite

from perturb_lm.sklearn_api import pilot
from perturb_lm.sklearn_api.datasets import file_checksum
from perturb_lm.sklearn_api.execution import completion_valid


@pytest.mark.parametrize("family", ["dinov2", "sapbert"])
def test_real_pilot_cli_preserves_rows_and_completion(request, family, tmp_path):
    spec, asset = request.getfixturevalue("assets")[family]
    data = tmp_path / "data"
    data.mkdir()
    payload = json.loads((pilot.ROOT / f"configs/pilots/{family}_v1.json").read_text())
    payload.update(execution="synthetic", synthetic_spec=asdict(spec))
    payload["dataset"].update(
        dataset="synthetic", version="fixture-1", synthetic=True, access="public"
    )
    ids = ["row-z", "row-a"]
    if family == "dinov2":
        rows = []
        for i, name in enumerate(ids):
            path = data / f"arbitrary-{i}.tif"
            pixels = np.random.default_rng(i).integers(1, 100, (4, 28, 28), dtype=np.uint16)
            imwrite(path, pixels, photometric="minisblack")
            rows.append({"record_id": name, "path": path.name, "sha256": file_checksum(path)})
        inventory = data / "image-inventory.json"
        inventory.write_text(json.dumps(rows))
        payload["image"] = {
            "axes": "CYX",
            "preprocessing": {
                "input_channels": ["c0", "c1", "c2", "c3"],
                "model_channels": ["c2", "c0", "c3"],
                "input_range": [0.0, 100.0],
                "mean": [0.5, 0.4, 0.3],
                "std": [0.2, 0.3, 0.4],
            },
        }
    else:
        inventory = data / "query-inventory.csv"
        pd.DataFrame(
            {
                "record_id": ids,
                "Metadata_pert_type": ["large cell", "small round nucleus"],
                "treatment": ["external-a", "external-b"],
                "Metadata_gene": ["GENEA", "GENEB"],
            }
        ).to_csv(inventory, index=False)
    payload["dataset"]["metadata_sha256"] = file_checksum(inventory)
    manifest = tmp_path / "pilot.json"
    manifest.write_text(json.dumps(payload))
    output = tmp_path / "result"
    env = dict(
        os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONPATH=str(pilot.ROOT / "src")
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "perturb_lm.sklearn_api.pilot",
            "run",
            "--manifest",
            str(manifest),
            "--data-root",
            str(data),
            "--asset-root",
            str(asset),
            "--out",
            str(output),
        ],
        check=True,
        env=env,
        timeout=60,
    )
    marker = json.loads((output / "complete.json").read_text())
    assert marker["provenance"]["scope"] == "synthetic_inference"
    assert marker["provenance"]["alignment"] == "none"
    assert completion_valid(output, marker["run_id"])
    with np.load(output / "embeddings.npz", allow_pickle=False) as result:
        assert result["record_ids"].tolist() == ids
        assert result["embeddings"].shape == (2, 24)
        assert result["embeddings"].dtype == np.float32
    # Same input/asset checksums, with no output overwrite or random fallback.
    with pytest.raises(FileExistsError):
        pilot.run_pilot(manifest, data_root=data, asset_root=asset, output=output)
    inventory.write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        pilot.run_pilot(manifest, data_root=data, asset_root=asset, output=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
