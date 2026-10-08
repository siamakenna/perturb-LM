"""Avoid rebuilding accepted artifacts for bookkeeping-only PR updates."""

import os
import re
import subprocess
import sys

BOOKKEEPING = {
    ".github/workflows/package.yml",
    "scripts/package_ci_changes.py",
    "tests/test_package_ci_changes.py",
    "docs/PHASE4_RELEASE_READINESS.md",
}


def needs_build(paths):
    # Unknown changes conservatively rebuild. No application/test exclusions.
    return any(path not in BOOKKEEPING for path in paths)


def comparison(event):
    if event.get("action") == "synchronize":
        before = event.get("before", "")
        if isinstance(before, str) and re.fullmatch(r"[0-9a-f]{40}", before):
            return before
    return None


def main():
    event = {
        "action": os.environ.get("PACKAGE_EVENT_ACTION", ""),
        "before": os.environ.get("PACKAGE_EVENT_BEFORE", ""),
    }
    before = comparison(event)
    rebuild = True  # Opened/reopened/manual/unknown events must validate.
    if before:
        result = subprocess.run(
            ["git", "diff", "--name-only", "-z", before, "HEAD"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            paths = [p.decode() for p in result.stdout.split(b"\0") if p]
            rebuild = needs_build(paths)

    print(f"rebuild={str(rebuild).lower()}")
    print(
        "Artifact rebuild required"
        if rebuild
        else "Bookkeeping-only update: retain prior artifact evidence; no rebuild",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
