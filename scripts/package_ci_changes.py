"""Require artifact validation on every package CI event."""

import sys


def main():
    print("rebuild=true")
    print("Artifact rebuild required", file=sys.stderr)


if __name__ == "__main__":
    main()
