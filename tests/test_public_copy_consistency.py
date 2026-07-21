from __future__ import annotations

import subprocess
import sys


def test_public_copy_consistency_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_public_copy_consistency.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
