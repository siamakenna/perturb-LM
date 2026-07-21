#!/usr/bin/env python3
"""Print a public-safe Perturb-LM environment report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.engineering.environment import environment_report_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(environment_report_json(), end="")


if __name__ == "__main__":
    main()
