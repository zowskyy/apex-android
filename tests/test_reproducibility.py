"""Reproducibility and golden baseline regression checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_golden_baseline_generation() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "tests" / "fixtures" / "golden-apk-baseline.json"
    subprocess.run(
        ["bash", str(root / "scripts" / "create-golden-apk.sh"), "tests/fixtures/sample_test.apk", str(out)],
        cwd=root,
        check=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "score" in payload
    assert "gate_passed" in payload


def test_sbom_generator() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "tests" / "fixtures" / "test-sbom.json"
    subprocess.run(
        [sys.executable, "scripts/release/generate_sbom.py", str(out)],
        cwd=root,
        check=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload.get("bomFormat") == "CycloneDX"
