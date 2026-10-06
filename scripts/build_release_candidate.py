#!/usr/bin/env python3
"""Build, check, and checksum a clean source revision. Does not publish anything."""

import argparse
import hashlib
import json
import platform
import runpy
import subprocess
import sys
from pathlib import Path


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if git(root, "status", "--porcelain"):
        parser.error("Build from a clean committed checkout")
    out = args.out.resolve()
    if out.exists():
        parser.error("Choose a new output directory")
    sha = git(root, "rev-parse", "HEAD")
    version = runpy.run_path(root / "src/perturb_lm/_version.py")["__version__"]
    out.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(out), str(root)], check=True)
    artifacts = sorted([*out.glob("*.whl"), *out.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise RuntimeError("Expected one wheel and one sdist")
    subprocess.run([sys.executable, "-m", "twine", "check", *map(str, artifacts)], check=True)
    if git(root, "rev-parse", "HEAD") != sha or git(root, "status", "--porcelain"):
        raise RuntimeError("Source changed during build; discard candidate")
    report = {
        "schema_version": 1,
        "version": version,
        "source_commit": sha,
        "source_unchanged": True,
        "python": platform.python_version(),
        "status": "BUILT_NOT_RELEASED",
        "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
    }
    (out / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in report["artifacts"].items())
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
