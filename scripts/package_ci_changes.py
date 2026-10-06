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
    raw = os.environ.get(name)
    if not raw:
        raise ValueError(f"Missing required environment variable: {name}")
    candidate = Path(raw).resolve()
    root_path = Path(root).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"{name} points outside trusted root: {candidate}") from exc
    return candidate


def safe_github_output_path():
    raw_output = os.environ["GITHUB_OUTPUT"]
    output_path = Path(raw_output).expanduser().resolve()

    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        workspace_path = Path(workspace).expanduser().resolve()
        try:
            output_path.relative_to(workspace_path)
    workspace_root = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    event_path = safe_env_path("GITHUB_EVENT_PATH", workspace_root)
    output_path = safe_env_path("GITHUB_OUTPUT", workspace_root)

    event = json.loads(event_path.read_text())
            raise ValueError("GITHUB_OUTPUT must be within GITHUB_WORKSPACE") from exc

    if output_path.exists() and not output_path.is_file():
        raise ValueError("GITHUB_OUTPUT must point to a file")

    return output_path


def comparison(event):
    if event.get("action") == "synchronize":
        before = event.get("before", "")
    with output_path.open("a") as handle:
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
    with safe_github_output_path().open("a") as handle:
        handle.write(f"rebuild={str(rebuild).lower()}\n")
    print(
        "Artifact rebuild required"
        if rebuild
        else "Bookkeeping-only update: retain prior artifact evidence; no rebuild"
    )


if __name__ == "__main__":
    main()
