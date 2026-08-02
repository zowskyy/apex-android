"""Native signing, SARIF, corpus, and interface-parity tests.

These cover capabilities APEX implements itself. None of them may depend on an
optional external tool being installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from apex.cli import build_parser, main
from apex.corpus.store import CorpusStore
from apex.providers.bootstrap import MANAGED_TOOLS, list_tools
from apex.reporting.sarif import security_scan_to_sarif
from apex.signing.display import format_signing_panel
from apex.signing.native import analyze_signatures
from apex.workflows import security_scan, verify_apk

ROOT = Path(__file__).resolve().parent.parent
REAL_DEX = ROOT / "core" / "dex_parser" / "tests" / "fixtures" / "classes.dex"

_JDK_SIGNING = bool(shutil.which("keytool") and shutil.which("jarsigner"))


@pytest.fixture(scope="module")
def signed_apk(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a genuinely v1-signed APK using the JDK toolchain."""
    if not _JDK_SIGNING:
        pytest.skip("keytool/jarsigner required to build a signed fixture")
    work = tmp_path_factory.mktemp("signed")
    apk = work / "signed.apk"
    with zipfile.ZipFile(apk, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "AndroidManifest.xml",
            b'<?xml version="1.0"?><manifest package="com.apex.signed"/>',
        )
        archive.writestr("classes.dex", REAL_DEX.read_bytes())
    keystore = work / "test.jks"
    subprocess.run(
        [
            "keytool", "-genkeypair", "-keystore", str(keystore),
            "-storepass", "android", "-keypass", "android",
            "-alias", "apexkey", "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "3650", "-dname", "CN=APEX Test, O=APEX, C=US",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "jarsigner", "-keystore", str(keystore),
            "-storepass", "android", "-keypass", "android",
            str(apk), "apexkey",
        ],
        check=True,
        capture_output=True,
    )
    return apk


def test_native_signing_extracts_full_certificate_detail(signed_apk: Path):
    result = analyze_signatures(signed_apk)
    assert result["provider"] == "apex-native"
    assert result["signed"] is True
    assert result["schemes"]["v1"] is True
    signer = result["signers"][0]
    assert signer["sha256"].count(":") == 31
    assert signer["sha1"].count(":") == 19
    assert "APEX Test" in signer["subject"]
    assert signer["self_signed"] is True
    assert signer["not_valid_after"] > signer["not_valid_before"]


@pytest.mark.skipif(not _JDK_SIGNING, reason="keytool required for cross-verification")
def test_native_fingerprint_matches_jdk_keytool(signed_apk: Path):
    """APEX's own fingerprint must equal the JDK's independent computation."""
    output = subprocess.run(
        ["keytool", "-printcert", "-jarfile", str(signed_apk)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected = next(
        line.split("SHA256:")[1].strip().lower()
        for line in output.splitlines()
        if "SHA256:" in line
    )
    assert analyze_signatures(signed_apk)["signers"][0]["sha256"] == expected


def test_signing_available_without_apksigner(signed_apk: Path, monkeypatch):
    """Certificate detail must never require an external tool."""
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("APEX_APKSIGNER", raising=False)
    panel = format_signing_panel(analyze_signatures(signed_apk))
    assert panel["fingerprint_sha256"]
    assert panel["subject"]
    assert panel["provider"] == "apex-native"


def test_verify_apk_reports_signing_panel(signed_apk: Path):
    result = verify_apk(signed_apk)
    assert result["schema_version"] == 3
    assert result["signing"]["fingerprint_sha256"]
    assert result["signing"]["trust_note"]
    assert any(item["operation"] == "verify.signatures" for item in result["provenance"])


def test_unsigned_apk_reports_absence_not_error(tmp_path: Path):
    from tests.test_workflows import make_apk

    apk = make_apk(tmp_path / "unsigned.apk")
    result = analyze_signatures(apk)
    assert result["signed"] is False
    assert any("no signing certificates" in item for item in result["warnings"])


def test_security_scan_sarif_document(tmp_path: Path):
    from tests.test_workflows import make_apk

    apk = make_apk(tmp_path / "malicious.apk", malicious=True)
    sarif = security_scan_to_sarif(security_scan(apk))
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "APEX"
    assert run["results"]
    assert all(item["ruleId"].startswith("apex/") for item in run["results"])
    assert {rule["id"] for rule in run["tool"]["driver"]["rules"]} >= {
        item["ruleId"] for item in run["results"]
    }


def test_cli_security_scan_sarif_format(tmp_path: Path, capsys):
    from tests.test_workflows import make_apk

    apk = make_apk(tmp_path / "clean.apk")
    assert main(["security-scan", str(apk), "--format", "sarif"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["$schema"].endswith("sarif-2.1.0.json")


def test_cli_signing_command(signed_apk: Path, capsys):
    assert main(["signing", str(signed_apk)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fingerprint_sha256"]


def test_cli_exposes_every_core_capability():
    """Interface parity: engine capabilities must be reachable from the CLI."""
    parser = build_parser()
    actions = [
        action
        for action in parser._actions
        if getattr(action, "choices", None) and isinstance(action.choices, dict)
    ]
    commands = set(actions[0].choices)
    required = {
        "inspect", "analyze", "decompile", "decode", "build", "verify",
        "roundtrip", "security-scan", "diff", "framework-check", "doctor",
        "icon", "export", "device", "bundle", "signing", "tools", "gui",
    }
    assert required <= commands


def test_managed_tool_catalog_is_declared():
    catalog = list_tools()
    names = {item["name"] for item in catalog["tools"]}
    assert names == set(MANAGED_TOOLS)
    assert all(item["license"] for item in catalog["tools"])
    assert all(item["source"].startswith("https://") for item in catalog["tools"])


def test_corpus_packages_listing(tmp_path: Path):
    store = CorpusStore(tmp_path / "corpus.db")
    device_id = store.upsert_device("serial-1", model="Pixel")
    run_id = store.start_sync(device_id, 0)
    store.register_artifact("sha-1", 10, "/tmp/base.apk")
    store.record_snapshot(
        run_id, device_id, 0, "com.example.app", 5, "1.5", "fp", "sha-1", "/tmp/r.json"
    )
    store.finish_sync(run_id, "ok")
    packages = store.packages()
    assert packages[0]["package_name"] == "com.example.app"
    assert packages[0]["serial"] == "serial-1"
    assert store.packages(serial="missing") == []
