"""Web API path containment and secret scanner tests."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from apex.analysis import ApexError
from apex.gate import run_hard_gate
from apex.secrets_scan import scan_apk_secrets
from apex.web import ApexWebHandler
from apex.web_security import resolve_client_package_path


def _make_apk(path: Path, extra_text: str = "") -> Path:
    manifest = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.apex.webtest" android:versionCode="1" android:versionName="1.0">
    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="34"/>
    <application android:label="Test"><activity android:name=".Main"/></application>
</manifest>"""
    dex = b"dex\n035\x00" + b"\x00" * 0x40
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("AndroidManifest.xml", manifest)
        zf.writestr("classes.dex", dex)
        if extra_text:
            zf.writestr("assets/config.txt", extra_text)
    return path


def test_resolve_client_path_rejects_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.apk"
    _make_apk(outside)
    with pytest.raises(ApexError, match="inside the APEX workspace"):
        resolve_client_package_path(str(outside), workspace, enforce_workspace=True)


def test_resolve_client_path_allows_workspace_file(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    inside = workspace / "app.apk"
    _make_apk(inside)
    resolved = resolve_client_package_path("app.apk", workspace, enforce_workspace=True)
    assert resolved == inside.resolve()


def test_scan_apk_secrets_detects_api_key(tmp_path: Path) -> None:
    apk = tmp_path / "leaky.apk"
    _make_apk(apk, extra_text="api_key = 'super_secret_value_12345'\n")
    hits = scan_apk_secrets(apk)
    assert any("secret-" in item.get("category", "") for item in hits)


def test_gate_includes_secrets_scanner(tmp_path: Path) -> None:
    apk = tmp_path / "gate.apk"
    _make_apk(apk, extra_text="api_key = 'super_secret_value_12345'\n")
    report = run_hard_gate(apk, msv=21, workspace=tmp_path)
    assert any(f.scanner == "secrets" for f in report.findings)


def test_web_open_rejects_path_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "web-ws"
    workspace.mkdir()
    outside = tmp_path / "outside.apk"
    _make_apk(outside)

    server = ThreadingHTTPServer(("127.0.0.1", 0), ApexWebHandler)
    server.workspace = str(workspace)  # type: ignore[attr-defined]
    server.enforce_workspace_paths = True  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        request = urllib.request.Request(
            f"{base}/api/open",
            data=json.dumps({"path": str(outside)}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request)
        assert exc.value.code == 400
        body = json.loads(exc.value.read().decode())
        assert "workspace" in body["error"].lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_open_allows_desktop_absolute_path(tmp_path: Path) -> None:
    apk = tmp_path / "fixture.apk"
    _make_apk(apk)
    workspace = tmp_path / "web-ws"
    workspace.mkdir()

    server = ThreadingHTTPServer(("127.0.0.1", 0), ApexWebHandler)
    server.workspace = str(workspace)  # type: ignore[attr-defined]
    server.enforce_workspace_paths = False  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        request = urllib.request.Request(
            f"{base}/api/open",
            data=json.dumps({"path": str(apk)}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        assert result["inspect"]["manifest"]["package"] == "com.apex.webtest"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
