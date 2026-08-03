"""Audit trail, compliance reports, and gate metadata tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from apex.gate import run_hard_gate
from apex.gate.audit_log import AuditLogger, immutable
from apex.gate.compliance_report import generate_compliance_report
from apex.gate.weights import load_scanner_metadata


@pytest.fixture()
def audit_dir(tmp_path: Path) -> Path:
    path = tmp_path / "audit"
    path.mkdir()
    os.environ["APEX_AUDIT_DIR"] = str(path)
    return path


def test_audit_log_immutability(audit_dir: Path, tmp_path: Path) -> None:
    apk = tmp_path / "mini.apk"
    import zipfile

    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"<manifest/>")
        zf.writestr("classes.dex", b"dex")

    run_hard_gate(apk, msv=21, stage="candidate")
    logger = AuditLogger()
    ok, msg = logger.verify_integrity()
    assert ok, msg
    assert immutable(logger.log_path)

    # Tamper should break chain (append invalid record)
    with logger.log_path.open("a", encoding="utf-8") as handle:
        handle.write('{"ts":"tampered","prev_hash":"broken"}\n')
    ok2, _ = logger.verify_integrity()
    assert not ok2


def test_compliance_report_from_audit(audit_dir: Path, tmp_path: Path) -> None:
    apk = tmp_path / "mini.apk"
    import zipfile

    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"<manifest/>")
        zf.writestr("classes.dex", b"dex")

    run_hard_gate(apk, msv=21, stage="candidate")
    report = generate_compliance_report(out_dir=audit_dir / "compliance")
    assert report["audit_integrity_ok"]
    assert report["metrics"]["gate_runs"] >= 1


def test_scanner_metadata_loaded() -> None:
    meta = load_scanner_metadata()
    assert "manifest" in meta
    assert meta["manifest"]["false_positive_rate"] == 0.02


def test_version_sync_atomic_flock() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "release" / "sync_version.sh"
    proc = subprocess.run(["bash", str(script), "0.4.11"], cwd=root, capture_output=True, text=True)
    assert proc.returncode == 0
