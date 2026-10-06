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


def safe_github_output_path():
    raw_output = os.environ["GITHUB_OUTPUT"]
    output_path = Path(raw_output).expanduser().resolve()

    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        workspace_path = Path(workspace).expanduser().resolve()
        try:
            output_path.relative_to(workspace_path)
        except ValueError as exc:
            raise ValueError("GITHUB_OUTPUT must be within GITHUB_WORKSPACE") from exc

    if output_path.exists() and not output_path.is_file():
        raise ValueError("GITHUB_OUTPUT must point to a file")

    return output_path


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
    with safe_github_output_path().open("a") as handle:
        handle.write(f"rebuild={str(rebuild).lower()}\n")
    print(
        "Artifact rebuild required"
        if rebuild
        else "Bookkeeping-only update: retain prior artifact evidence; no rebuild"
    )


if __name__ == "__main__":
    main()
