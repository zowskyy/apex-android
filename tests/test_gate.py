"""Tests for apex gate hard-gate runner."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from apex.gate import run_hard_gate
from apex.gate.models import GateStatus


@pytest.fixture(scope="module")
def sample_apk() -> Path:
    path = Path(__file__).resolve().parent / "fixtures" / "sample_test.apk"
    if not path.is_file():
        pytest.skip("sample_test.apk fixture missing")
    return path


def test_hard_gate_passes_sample_apk(sample_apk: Path, tmp_path: Path) -> None:
    report = run_hard_gate(sample_apk, msv=21, stage="candidate", workspace=tmp_path)
    assert report.gate_passed
    assert report.score >= 60
    assert not report.blocking
    assert any(f.status == GateStatus.PASS for f in report.findings)


def test_hard_gate_fails_low_msv(sample_apk: Path, tmp_path: Path) -> None:
    report = run_hard_gate(sample_apk, msv=99, stage="candidate", workspace=tmp_path)
    assert not report.gate_passed
    assert report.blocking


def test_hard_gate_resolves_release_zip(sample_apk: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "APEX-Mobile-gate-test-android.zip"
    with zipfile.ZipFile(bundle, "w") as outer:
        outer.write(sample_apk, "APEX-Mobile-gate-test.apk")
        outer.writestr("INSTALL.txt", "notes")
    report = run_hard_gate(bundle, msv=21, workspace=tmp_path)
    assert report.resolved_from == "APEX-Mobile-gate-test.apk"
    assert report.gate_passed


def test_gate_cli_ci_mode(sample_apk: Path, tmp_path: Path) -> None:
    from apex.cli import main

    out = tmp_path / "gate-out.json"
    code = main(["gate", str(sample_apk), "--msv", "21", "--ci", "-o", str(out)])
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["gate_passed"]
