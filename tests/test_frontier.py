"""Tests for frontier capabilities: intel, iOS, SBOM, secrets, posture, optimization."""

from __future__ import annotations

import plistlib
import struct
import zipfile
from pathlib import Path

from apex.analysis import _zip_inventory_native, zip_inventory
from apex.intel.detect import detect_android, detect_ios, summarize_detections
from apex.intel.privacy_posture import assess_posture
from apex.intel.signatures import signature_stats
from apex.ios.ipa import inspect_ipa, is_ipa
from apex.ios.macho import parse_macho
from apex.ios.privacy_manifest import analyze_privacy_manifest
from apex.reporting.sarif import security_scan_to_sarif
from apex.reporting.sbom import build_sbom
from apex.security.secrets import redact, scan_secrets, shannon_entropy
from apex.workflows import generate_sbom, privacy_report, scan_trackers, security_scan


def _build_macho() -> bytes:
    mh_magic_64 = 0xFEEDFACF
    cpu_arm64 = 0x0100000C
    mh_pie = 0x200000
    lc_load_dylib = 0x0C
    name = b"@rpath/GoogleMobileAds.framework/GoogleMobileAds\x00"
    name_off = 24
    cmdsize = name_off + len(name)
    pad = (8 - (cmdsize % 8)) % 8
    cmdsize += pad
    lc = struct.pack("<IIIIII", lc_load_dylib, cmdsize, name_off, 0, 0, 0) + name + b"\x00" * pad
    header = struct.pack(
        "<IiiIIII I", mh_magic_64, cpu_arm64, 0, 2, 1, len(lc), mh_pie, 0
    )
    return header + lc + b"__stack_chk_guard\x00_objc_release\x00"


def _build_ipa(path: Path, *, tracking: bool = False) -> None:
    info = plistlib.dumps(
        {
            "CFBundleIdentifier": "com.example.app",
            "CFBundleName": "Example",
            "CFBundleShortVersionString": "1.2",
            "CFBundleVersion": "34",
            "MinimumOSVersion": "15.0",
            "CFBundleExecutable": "Example",
            "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        }
    )
    priv = plistlib.dumps(
        {
            "NSPrivacyTracking": tracking,
            "NSPrivacyTrackingDomains": [],
            "NSPrivacyAccessedAPITypes": [
                {
                    "NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryUserDefaults",
                    "NSPrivacyAccessedAPITypeReasons": [],
                }
            ],
        }
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Payload/Example.app/Info.plist", info)
        archive.writestr("Payload/Example.app/Example", _build_macho())
        archive.writestr("Payload/Example.app/PrivacyInfo.xcprivacy", priv)
        archive.writestr(
            "Payload/Example.app/Frameworks/AppsFlyerLib.framework/AppsFlyerLib", b"\x00"
        )


def test_signature_stats_loaded():
    stats = signature_stats()
    assert stats["tracker_count"] > 10
    assert stats["library_count"] > 5


def test_detect_android_tracker_and_library():
    dets = detect_android(
        ["com.google.android.gms.ads.MobileAds", "okhttp3.OkHttpClient", "com.myapp.Main"]
    )
    ids = {d["id"]: d["kind"] for d in dets}
    assert ids["google_admob"] == "tracker"
    assert ids["okhttp"] == "library"
    summary = summarize_detections(dets)
    assert summary["tracker_count"] == 1
    assert summary["library_count"] == 1
    assert "Advertisement" in summary["tracker_categories"]


def test_macho_hardening_flags():
    parsed = parse_macho(_build_macho())
    assert parsed["valid"]
    assert parsed["pie"]
    assert parsed["has_stack_canary"]
    assert parsed["has_arc"]
    assert "GoogleMobileAds" in parsed["frameworks"]


def test_macho_rejects_non_macho():
    assert parse_macho(b"not a macho at all")["valid"] is False


def test_detect_ios_from_frameworks():
    dets = detect_ios(["GoogleMobileAds", "AppsFlyerLib", "UnknownKit"])
    names = {d["id"] for d in dets}
    assert "google_admob" in names
    assert "appsflyer" in names


def test_privacy_manifest_required_reason_finding():
    raw = plistlib.dumps(
        {
            "NSPrivacyTracking": True,
            "NSPrivacyAccessedAPITypes": [
                {"NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryDiskSpace"}
            ],
        }
    )
    result = analyze_privacy_manifest(raw)
    assert result["valid"]
    assert any("Required Reason API" in f["message"] for f in result["findings"])


def test_inspect_ipa_end_to_end(tmp_path: Path):
    ipa = tmp_path / "example.ipa"
    _build_ipa(ipa)
    assert is_ipa(ipa)
    report = inspect_ipa(ipa)
    assert report["app"]["bundle_id"] == "com.example.app"
    tracker_ids = {t["id"] for t in report["trackers"]}
    assert {"google_admob", "appsflyer"} <= tracker_ids
    assert any(f["category"] == "ios-transport-security" for f in report["findings"])


def test_ios_posture_discrepancy(tmp_path: Path):
    ipa = tmp_path / "example.ipa"
    _build_ipa(ipa, tracking=False)
    report = inspect_ipa(ipa)
    detections = report["trackers"] + report["libraries"]
    posture = assess_posture(
        platform="ios",
        detections=detections,
        cleartext=True,
        privacy_manifest=report["privacy_manifest"],
    )
    assert posture["grade"] == "F"
    assert any("NSPrivacyTracking=false" in d["message"] for d in posture["discrepancies"])


def test_sbom_cyclonedx_structure():
    detections = detect_android(["com.google.android.gms.ads.X", "okhttp3.Y"])
    sbom = build_sbom(
        {"name": "com.example", "version": "1.0", "platform": "android", "sha256": "ab" * 32},
        detections,
    )
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert len(sbom["components"]) == 2
    tracker_comp = next(c for c in sbom["components"] if c["bom-ref"].startswith("tracker:"))
    assert any(p["name"] == "apex:tracker" for p in tracker_comp["properties"])


def test_secret_detection_and_redaction():
    entropy = shannon_entropy("AKIAIOSFODNN7EXAMPLE")
    assert entropy > 3.0
    findings = scan_secrets(["key=AKIAIOSFODNN7EXAMPLE", "nothing here"], source="test")
    assert findings
    assert findings[0]["category"] == "secret-material"
    assert "AKIAIOSFODNN7EXAMPLE" not in findings[0]["evidence"]
    assert redact("AKIAIOSFODNN7EXAMPLE").startswith("AKIA")


def test_posture_grade_clean_app():
    posture = assess_posture(platform="android", permissions=[], detections=[], cleartext=False)
    assert posture["grade"] == "A"
    assert posture["score"] == 100


def test_columnar_inventory_matches_python(tmp_path: Path):
    apk = Path("tests/fixtures/sample_test.apk")
    if not apk.is_file():
        import subprocess
        import sys

        subprocess.run([sys.executable, "scripts/generate_test_apk.py"], check=True)
    native = _zip_inventory_native(apk)
    assert native is not None
    import apex.analysis as analysis

    saved = analysis._native_zip
    analysis._native_zip = None
    try:
        pure = zip_inventory(apk)
    finally:
        analysis._native_zip = saved
    assert native["entry_count"] == pure["entry_count"]
    assert native["files"] == pure["files"]


def test_security_scan_has_masvs_and_sarif():
    apk = Path("tests/fixtures/sample_test.apk")
    scan = security_scan(apk)
    for finding in scan["findings"]:
        assert "masvs" in finding
        assert "cwe" in finding
    sarif = security_scan_to_sarif(scan)
    assert sarif["version"] == "2.1.0"


def test_workflow_helpers_android():
    apk = Path("tests/fixtures/sample_test.apk")
    trackers = scan_trackers(apk)
    assert trackers["platform"] == "android"
    sbom = generate_sbom(apk)
    assert sbom["bomFormat"] == "CycloneDX"
    privacy = privacy_report(apk)
    assert privacy["privacy_posture"]["platform"] == "android"


def test_cli_ios_and_sbom(tmp_path: Path, capsys):
    from apex.cli import main

    ipa = tmp_path / "example.ipa"
    _build_ipa(ipa)
    assert main(["sbom", str(ipa)]) == 0
    out = capsys.readouterr().out
    assert "CycloneDX" in out
    assert main(["trackers", str(ipa)]) == 0
    assert "tracker_count" in capsys.readouterr().out
