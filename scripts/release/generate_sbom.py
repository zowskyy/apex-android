#!/usr/bin/env python3
"""Generate SBOM for APEX release (CycloneDX when available, JSON fallback)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _fallback_sbom(out: Path) -> dict:
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    import re

    ver = re.search(r'^version = "([^"]+)"', pyproject, flags=re.M)
    version = ver.group(1) if ver else "unknown"
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "apex-android",
                "version": version,
            }
        },
        "components": [
            {"type": "library", "name": "apex-android", "version": version},
            {"type": "library", "name": "apex_zip_reader", "version": "0.1.0"},
            {"type": "library", "name": "apex_dex_reader", "version": "0.1.0"},
        ],
        "generator": "apex generate_sbom fallback",
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "sbom.json")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "cyclonedx_py",
                "environment",
                "--output-format",
                "json",
                "--output-file",
                str(out),
            ],
            cwd=_ROOT,
            check=True,
            capture_output=True,
        )
        print(f"SBOM (cyclonedx): {out}")
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        _fallback_sbom(out)
        print(f"SBOM (fallback): {out}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
