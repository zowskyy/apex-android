"""Version sync guard used in CI before release."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_version_sources_in_sync() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "release" / "check_version_sync.sh"
    result = subprocess.run(["bash", str(script)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
