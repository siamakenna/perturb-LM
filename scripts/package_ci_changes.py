"""Avoid rebuilding accepted artifacts for bookkeeping-only PR updates."""

import json
import os
import re
import subprocess
from pathlib import Path

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
        if re.fullmatch(r"[0-9a-f]{40}", before):
            return before
    return None


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
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
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as handle:
        handle.write(f"rebuild={str(rebuild).lower()}\n")
    print(
        "Artifact rebuild required"
        if rebuild
        else "Bookkeeping-only update: retain prior artifact evidence; no rebuild"
    )


if __name__ == "__main__":
    main()
