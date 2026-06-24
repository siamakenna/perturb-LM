#!/usr/bin/env python3
"""Safe RxRx metadata, embedding, and image downloader scaffold."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.rxrx_common import build_download_plan, download_plans, parse_download_values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument(
        "--download",
        action="append",
        required=True,
        help="Resource to download: metadata, embeddings, images. May be repeated or comma-separated.",
    )
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without downloading.")
    parser.add_argument(
        "--confirm-large-download",
        action="store_true",
        help="Required when --download includes images.",
    )
    args = parser.parse_args()

    try:
        downloads = parse_download_values(args.download)
        plans = build_download_plan(args.dataset, downloads, args.out)
        download_plans(plans, dry_run=args.dry_run, confirm_large_download=args.confirm_large_download)
    except ValueError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
