"""Dry-run validation for a user-supplied dataset manifest; no download or copy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from perturb_lm.sklearn_api.adapters import AdapterConfig, LocalDatasetAdapter
from perturb_lm.sklearn_api.datasets import DatasetManifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--include-representations", action="store_true")
    args = parser.parse_args()
    payload = yaml.safe_load(args.manifest.read_text())
    manifest = DatasetManifest(**payload["manifest"] if "manifest" in payload else payload)
    config = AdapterConfig.from_dict(payload.get("adapter", {}))
    result = LocalDatasetAdapter(manifest, args.root, config).validate(args.include_representations)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
