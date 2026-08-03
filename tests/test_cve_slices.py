"""Tests for API watch, NETSEC, LINT, dependency/CVE, and full gate integration."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from apex.dependency_scan import load_cve_db, scan_apk_dependencies, update_cve_db_from_bundle
from apex.gate import run_hard_gate
from apex.gate.models import GateStatus, normalize_status
from apex.gate.weights import load_scanner_weights, validate_weights
from apex.lint_scan import scan_java_tree
from apex.native_scan import inspect_elf
from apex.netsec_scan import scan_network_security
from tests.test_workflows import make_apk


def test_gate_weights_blueprint_sum() -> None:
    weights = load_scanner_weights()
    validate_weights(weights)
    expected = {
        "manifest",
        "dex",
        "security",
        "secrets",
        "native",
        "api_watch",
        "netsec",
        "lint",
        "dependency",
        "obfuscation",
    }
    assert set(weights.keys()) == expected


def test_normalize_low_confidence_fail_to_warn() -> None:
    assert normalize_status(GateStatus.FAIL, "LOW") == GateStatus.WARN
    assert normalize_status(GateStatus.FAIL, "HIGH") == GateStatus.FAIL


def test_netsec_user_ca_fixture(tmp_path: Path) -> None:
    apk = tmp_path / "netsec.apk"
    nsc = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config>
    <trust-anchors>
      <certificates src="user"/>
    </trust-anchors>
  </base-config>
</network-security-config>"""
    manifest = (
        b"<manifest xmlns:android='http://schemas.android.com/apk/res/android' package='t'>"
        b"<application android:networkSecurityConfig='@xml/network_security_config'/>"
        b"</manifest>"
    )
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", manifest)
        zf.writestr("res/xml/network_security_config.xml", nsc)
    hits = scan_network_security(apk)
    assert any(item.get("category") == "netsec-user-ca" for item in hits)


def test_lint_trust_all_trustmanager(tmp_path: Path) -> None:
    java_root = tmp_path / "java"
    java_root.mkdir()
    bad = java_root / "Ssl.java"
    bad.write_text(
        "class S { void checkServerTrusted() { return; } }",
        encoding="utf-8",
    )
    hits = scan_java_tree(
        java_root,
        [
            {
                "id": "trust-all-trustmanager",
                "pattern": r"checkServerTrusted\([^)]*\)\s*\{[^}]*return\s*;",
                "message": "TrustManager may accept all certificates",
                "applies_to": "**/*.java",
                "severity": "high",
            }
        ],
    )
    assert any("trust-all-trustmanager" in item.get("category", "") for item in hits)


def test_dependency_prefix_only_advisory(tmp_path: Path) -> None:
    apk = make_apk(tmp_path / "dep.apk")
    with patch(
        "apex.dependency_scan.collect_apk_dex_index",
        return_value={
            "classes": [{"name": "okhttp3.internal.http.BridgeInterceptor"}],
            "strings": [],
            "edges": [],
        },
    ):
        hits = scan_apk_dependencies(apk)
    assert hits
    assert all(item.get("confidence") == "prefix-only" for item in hits)


def test_dependency_version_confirmed_cve(tmp_path: Path) -> None:
    apk = make_apk(tmp_path / "dep2.apk")
    with patch(
        "apex.dependency_scan.collect_apk_dex_index",
        return_value={
            "classes": [{"name": "okhttp3.OkHttpClient"}],
            "strings": ["okhttp/4.8.0"],
            "edges": [],
        },
    ):
        hits = scan_apk_dependencies(apk)
    assert any(item.get("confidence") == "version-confirmed" for item in hits)
    assert any("CVE" in item.get("message", "") for item in hits)


def test_native_16k_fail_when_min_sdk_35() -> None:
    elf = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8 + bytes(range(48))
    report = inspect_elf(elf, min_sdk=35)
    assert any(item.get("category") == "native-16k-align" for item in report["findings"])
    align = next(item for item in report["findings"] if item["category"] == "native-16k-align")
    assert align["severity"] == "high"


def test_update_cve_db_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = update_cve_db_from_bundle()
    assert path.is_file()
    db = load_cve_db()
    assert db.get("libraries")


def test_hard_gate_runs_all_scanners(sample_apk: Path, tmp_path: Path) -> None:
    report = run_hard_gate(sample_apk, msv=21, stage="candidate", workspace=tmp_path)
    scanners = {f.scanner for f in report.findings}
    assert "api_watch" in scanners
    assert "netsec" in scanners
    assert "dependency" in scanners
    assert "obfuscation" in scanners
    # dependency/CVE is advisory — should not block by itself
    dep_fails = [f for f in report.findings if f.scanner == "dependency" and f.status == GateStatus.FAIL]
    assert not dep_fails


@pytest.fixture(scope="module")
def sample_apk() -> Path:
    path = Path(__file__).resolve().parent / "fixtures" / "sample_test.apk"
    if not path.is_file():
        pytest.skip("sample_test.apk fixture missing")
    return path


def test_gate_report_includes_confidence(sample_apk: Path, tmp_path: Path) -> None:
    report = run_hard_gate(sample_apk, msv=21, workspace=tmp_path)
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["findings"]
    assert "confidence" in payload["findings"][0]
