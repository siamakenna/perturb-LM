#!/usr/bin/env python3
"""Audit local JUMP CPJUMP1 pilot metadata and profile files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    EXPECTED_BATCH,
    EXPECTED_PROFILE_KIND,
    audit_jump_pilot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/jump_pilot"))
    parser.add_argument("--expected-batch", default=EXPECTED_BATCH)
    parser.add_argument("--expected-profile-kind", default=EXPECTED_PROFILE_KIND)
    parser.add_argument("--out", type=Path, default=Path("outputs/jump_pilot_inventory.json"))
    args = parser.parse_args()

    inventory = audit_jump_pilot(
        args.data_root,
        expected_batch=args.expected_batch,
        expected_profile_kind=args.expected_profile_kind,
    )
    text = json.dumps(inventory, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"Wrote JUMP pilot inventory to {args.out}")
    print(text)


if __name__ == "__main__":
    main()
