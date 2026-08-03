from __future__ import annotations

import json
import threading
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from apex.analysis import dex_metadata, inspect_apk
from apex.cli import main
from apex.web import ApexWebHandler
from apex.workflows import (
    analyze_apk,
    build_project,
    decode_apk,
    decompile_apk,
    diff_apks,
    roundtrip_verify,
    security_scan,
    verify_apk,
)

ROOT = Path(__file__).resolve().parent.parent
REAL_DEX = ROOT / "core" / "dex_parser" / "tests" / "fixtures" / "classes.dex"
MANIFEST = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
 package="com.apex.fixture" android:versionCode="7" android:versionName="1.2">
 <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35"/>
 <uses-permission android:name="android.permission.INTERNET"/>
 <application android:label="Fixture" android:allowBackup="false">
  <activity android:name=".MainActivity" android:exported="true">
   <intent-filter>
    <action android:name="android.intent.action.MAIN"/>
    <category android:name="android.intent.category.LAUNCHER"/>
   </intent-filter>
  </activity>
 </application>
</manifest>"""


def make_apk(path: Path, *, nested: bool = False, malicious: bool = False) -> Path:
    prefix = "base/" if nested else ""
    manifest_name = f"{prefix}manifest/AndroidManifest.xml" if nested else "AndroidManifest.xml"
    dex_name = f"{prefix}dex/classes.dex" if nested else "classes.dex"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(manifest_name, MANIFEST)
        archive.writestr(dex_name, REAL_DEX.read_bytes())
        archive.writestr(f"{prefix}assets/message.txt", b"hello")
        if malicious:
            archive.writestr("../../escape.txt", b"blocked")
    return path


def test_real_dex_metadata_has_classes_methods_and_calls():
    metadata = dex_metadata(REAL_DEX.read_bytes())
    names = {item["name"] for item in metadata["classes"]}
    methods = {(item["class"], item["name"]) for item in metadata["methods"]}
    assert len(names) == 7
    assert "com.apex.testapp.MainActivity" in names
    assert ("com.apex.testapp.MainActivity", "onCreate") in methods
    assert metadata["edges"]


def test_inspect_apk_reads_manifest_without_extraction(tmp_path: Path):
    apk = make_apk(tmp_path / "fixture.apk")
    result = inspect_apk(apk, include_files=True)
    assert result["manifest"]["package"] == "com.apex.fixture"
    assert result["manifest"]["main_activity"] == "com.apex.fixture.MainActivity"
    assert result["dex_files"] == ["classes.dex"]
    assert result["native_abis"] == []
    assert len(result["files"]) == 3


def test_aab_nested_manifest_and_dex_are_supported(tmp_path: Path):
    bundle = make_apk(tmp_path / "fixture.aab", nested=True)
    inspected = inspect_apk(bundle)
    assert inspected["format"] == "aab"
    assert inspected["manifest"]["package"] == "com.apex.fixture"
    assert inspected["dex_files"] == ["base/dex/classes.dex"]
    result = decompile_apk(bundle, tmp_path / "source")
    assert len(result["classes"]) == 7


def test_full_analysis_and_decompile_real_dex(tmp_path: Path):
    apk = make_apk(tmp_path / "fixture.apk")
    report = analyze_apk(apk, tmp_path / "report")
    assert report["reachability"]["class_count"] == 7
    assert report["reachability"]["method_count"] == 10
    assert (tmp_path / "report" / "report.html").is_file()
    decompiled = decompile_apk(apk, tmp_path / "source")
    assert len(decompiled["classes"]) == 7
    assert len(list((tmp_path / "source" / "java").rglob("*.java"))) == 7
    main_source = tmp_path / "source" / "java" / "com" / "apex" / "testapp" / "MainActivity.java"
    assert "class MainActivity" in main_source.read_text(encoding="utf-8")


def test_raw_decode_build_roundtrip_is_payload_identical(tmp_path: Path):
    apk = make_apk(tmp_path / "fixture.apk")
    project = tmp_path / "project"
    metadata = decode_apk(apk, project, backend="raw")
    assert metadata["backend"] == "raw"
    assert (project / "decoded" / "AndroidManifest.xml").is_file()
    built = build_project(project, tmp_path / "rebuilt.apk")
    assert built["backend"] == "raw"
    difference = diff_apks(apk, tmp_path / "rebuilt.apk")
    assert difference["files"] == {"added": [], "removed": [], "changed": []}
    assert verify_apk(tmp_path / "rebuilt.apk")["valid"] is True
    roundtrip = roundtrip_verify(apk, tmp_path / "roundtrip")
    assert roundtrip["verdict"] == "PASS"


def test_security_scan_reports_traversal(tmp_path: Path):
    apk = make_apk(tmp_path / "malicious.apk", malicious=True)
    result = security_scan(apk)
    assert result["verdict"] == "HIGH_RISK"
    assert any(item["category"] == "path-traversal" for item in result["findings"])


def test_cli_inspect_and_security_exit_codes(tmp_path: Path, capsys):
    clean = make_apk(tmp_path / "clean.apk")
    malicious = make_apk(tmp_path / "malicious.apk", malicious=True)
    assert main(["inspect", str(clean)]) == 0
    assert json.loads(capsys.readouterr().out)["manifest"]["package"] == "com.apex.fixture"
    assert main(["security-scan", str(malicious)]) == 4


def test_web_health_and_open_api(tmp_path: Path):
    apk = make_apk(tmp_path / "fixture.apk")
    server = ThreadingHTTPServer(("127.0.0.1", 0), ApexWebHandler)
    server.workspace = str(tmp_path / "web")  # type: ignore[attr-defined]
    server.enforce_workspace_paths = False  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(f"{base}/api/health") as response:
            assert json.load(response)["ready"] is True
        request = urllib.request.Request(
            f"{base}/api/open",
            data=json.dumps({"path": str(apk)}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        assert result["inspect"]["manifest"]["package"] == "com.apex.fixture"
        assert len(result["dex"]["classes"]) == 7
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
