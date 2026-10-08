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


def safe_env_path(name, root):
    """Require GitHub-provided file-command paths to remain inside runner temp."""
    raw = os.environ.get(name)
    if not raw:
        raise ValueError(f"Missing required environment variable: {name}")
    candidate = Path(raw).expanduser().resolve()
    root_path = Path(root).expanduser().resolve()
    if not candidate.is_relative_to(root_path):
        raise ValueError(f"{name} points outside trusted runner temp")
    if not candidate.is_file():
        raise ValueError(f"{name} must point to a regular file")
    return candidate


def comparison(event):
    if event.get("action") == "synchronize":
        before = event.get("before", "")
        if isinstance(before, str) and re.fullmatch(r"[0-9a-f]{40}", before):
            return before
    return None


def main():
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise ValueError("RUNNER_TEMP is required for GitHub file-command paths")
    event_path = safe_env_path("GITHUB_EVENT_PATH", runner_temp)
    output_path = safe_env_path("GITHUB_OUTPUT", runner_temp)

    event = json.loads(event_path.read_text(encoding="utf-8"))
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
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"rebuild={str(rebuild).lower()}\n")
    print(
        "Artifact rebuild required"
        if rebuild
        else "Bookkeeping-only update: retain prior artifact evidence; no rebuild"
    )


if __name__ == "__main__":
    main()
