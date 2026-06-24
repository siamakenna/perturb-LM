#!/usr/bin/env python3
"""Download a lightweight subset of JUMP pilot profile files.

The CPJUMP1 profile artifacts in GitHub are stored with Git LFS. This script
uses GitHub's media endpoint for profile files and raw GitHub URLs for small
metadata files, avoiding a hard dependency on git-lfs or the AWS CLI.
"""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import certifi


REPO = "jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1"
BRANCH = "main"
API_BASE = f"https://api.github.com/repos/{REPO}/contents"
MEDIA_BASE = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

DEFAULT_METADATA = {
    "benchmark/output/experiment-metadata.tsv": "experiment-metadata.tsv",
    "metadata/external_metadata/JUMP-Target-1_compound_metadata.tsv": "JUMP-Target-1_compound_metadata.tsv",
    "metadata/external_metadata/JUMP-Target-1_compound_metadata_targets.tsv": "JUMP-Target-1_compound_metadata_targets.tsv",
    "metadata/external_metadata/JUMP-Target-1_crispr_metadata.tsv": "JUMP-Target-1_crispr_metadata.tsv",
    "metadata/external_metadata/JUMP-Target-1_orf_metadata.tsv": "JUMP-Target-1_orf_metadata.tsv",
}


def fetch_json(url: str) -> list[dict]:
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "biomorph-search"})
    with urlopen(req, context=SSL_CONTEXT) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, dest: Path, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "biomorph-search"})
            with urlopen(req, context=SSL_CONTEXT) as response, dest.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            return
        except HTTPError as exc:
            last_error = exc
            if exc.code == 404:
                raise
        except Exception as exc:  # pragma: no cover - defensive retry path
            last_error = exc
        time.sleep(1 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def list_plate_dirs(batch: str) -> list[str]:
    url = f"{API_BASE}/profiles/{batch}?ref={BRANCH}"
    items = fetch_json(url)
    return sorted(item["name"] for item in items if item.get("type") == "dir")


def download_metadata(root: Path) -> None:
    metadata_dir = root / "metadata"
    for remote_path, local_name in DEFAULT_METADATA.items():
        download(f"{RAW_BASE}/{remote_path}", metadata_dir / local_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="2020_11_04_CPJUMP1")
    parser.add_argument("--profile-kind", default="normalized_feature_select_negcon_batch")
    parser.add_argument("--plate-limit", type=int, default=12)
    parser.add_argument("--out-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--manifest", type=Path, default=Path("data/interim/jump_pilot_profile_files.csv"))
    args = parser.parse_args()

    plates = list_plate_dirs(args.batch)
    if args.plate_limit:
        plates = plates[: args.plate_limit]

    rows: list[dict[str, str]] = []
    for plate in plates:
        filename = f"{plate}_{args.profile_kind}.csv.gz"
        remote_path = f"profiles/{args.batch}/{plate}/{filename}"
        url = f"{MEDIA_BASE}/{remote_path}"
        local_path = args.out_root / "profiles" / args.batch / plate / filename
        download(url, local_path)
        rows.append(
            {
                "batch": args.batch,
                "plate": plate,
                "profile_kind": args.profile_kind,
                "path": str(local_path),
                "url": url,
            }
        )

    download_metadata(args.out_root)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["batch", "plate", "profile_kind", "path", "url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Downloaded {len(rows)} profile files")
    print(f"Wrote manifest: {args.manifest}")


if __name__ == "__main__":
    main()
