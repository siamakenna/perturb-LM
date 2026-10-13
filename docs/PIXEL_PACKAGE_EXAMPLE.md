# Executed installed image example

This script runs in a fresh `perturb-lm[pixel]` artifact environment outside
the checkout. Synthetic fixtures exercise the actual installed console script.
The reference and query TIFFs are separate. No biological metadata is supplied.

```python
import csv
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from tifffile import imwrite

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    yy, xx = np.mgrid[:64, :64]
    for name, radius in [("reference-a", 4), ("reference-b", 6), ("query", 5)]:
        plane = np.zeros((64, 64), dtype=np.uint16)
        for y, x in [(16, 16), (46, 46)]:
            plane[(yy-y)**2 + (xx-x)**2 <= radius**2] = 2000
        imwrite(work / f"{name}.tif", np.stack([plane, plane // 2]),
                photometric="minisblack")
    common = ["--axes", "CYX", "--channels", "c0,c1"]
    def cli(*arguments):
        subprocess.run(["perturb-lm", "images", *arguments], cwd=work, check=True)
    cli("fit", "reference-a.tif", "reference-b.tif", *common,
        "--image-id", "ref-a", "--image-id", "ref-b", "--out", "reference")
    before = (work / "reference/state.json").read_bytes()
    cli("analyze", "query.tif", *common, "--out", "raw")
    cli("analyze", "query.tif", *common, "--state", "reference/state.json",
        "--out", "scaled")
    cli("search", "query.tif", *common, "--reference", "reference",
        "--image-id", "query-a", "--top-k", "2", "--out", "query-results")
    assert before == (work / "reference/state.json").read_bytes()
    for artifact in ["measurements.csv", "masks/000000.tif", "neighbors.csv",
                     "raw_features.csv", "scaled_features.csv", "report.html"]:
        assert (work / "query-results" / artifact).is_file()
    with (work / "query-results/neighbors.csv").open() as handle:
        neighbors = list(csv.DictReader(handle))
    assert {row["reference_id"] for row in neighbors} == {"ref-a", "ref-b"}
    assert {row["query_id"] for row in neighbors} == {"query-a"}
    assert json.loads((work / "query-results/run.json").read_text())["n_accepted"] == 1
```

For your own TIFFs use persistent new output directories and open
`query-results/report.html` locally. Areas/perimeters use pixel units,
intensities retain decoded source units, and previews are display-only.
Paths/IDs are provenance, never predictors. Channel names and axes specify
technical interpretation explicitly. Similarity and synthetic tests establish
neither biological relevance nor freedom from pixel-encoded acquisition effects.
