#!/usr/bin/env python3
"""Read-only query identifiability audit using unchanged M0 renderers."""

from __future__ import annotations

import argparse
from pathlib import Path

from audit_phase5_cpjump1 import ignored_output

from perturb_lm.audits.cohort import load_profiles, write_json
from perturb_lm.audits.queries import audit_queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("outputs/phase5/queries"))
    args = parser.parse_args()
    out = ignored_output(args.out)
    profiles, manifest = load_profiles(args.data_root)
    if profiles.empty:
        raise ValueError("The historical batch's local profiles are unavailable")
    result, groups = audit_queries(profiles)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "query_summary.json", result)
    write_json(out / "profile_manifest.json", manifest)
    groups.to_csv(out / "query_groups.csv", index=False)
    for policy, value in result.items():
        if isinstance(value, dict) and "unique_strings" in value:
            print(
                policy, value["total_queries"], value["unique_strings"], value["collision_groups"]
            )


if __name__ == "__main__":
    main()
