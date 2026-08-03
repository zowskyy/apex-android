"""Blueprint slice tests: SECRETS-2, weights registry, native ELF, dex watch."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

from apex.gate.weights import load_scanner_weights, validate_weights
from apex.native_scan import inspect_elf, scan_apk_native_libs
from apex.secrets_scan import scan_apk_secrets, scan_dex_secrets, scan_text_for_secrets
from tests.test_workflows import make_apk


def test_gate_weights_sum_to_one() -> None:
    weights = load_scanner_weights()
    validate_weights(weights)
    assert set(weights.keys()) >= {
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


def test_scan_text_for_secrets_attributes_source() -> None:
    hits = scan_text_for_secrets(
        "api_key = 'super_secret_value_12345'",
        source="resource-file:assets/config.txt",
    )
    assert hits
    assert hits[0]["source"].startswith("resource-file:")


def test_secrets_2_dex_string_pool() -> None:
    needle = "AIzaSyDUMMYKEYFORAPEXSECRETSCAN1234567890ab"
    with patch("apex.secrets_scan.dex_string_pool", return_value=[needle]):
        hits = scan_dex_secrets(b"fake", "classes.dex")
    assert hits
    assert all("dex-string-pool" in item["source"] for item in hits)


def test_scan_apk_secrets_resource_and_dex_paths(tmp_path: Path) -> None:
    apk = tmp_path / "both.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr(
            "AndroidManifest.xml",
            b"<manifest package='c' xmlns:android='http://schemas.android.com/apk/res/android'/>",
        )
        zf.writestr("classes.dex", b"dex\n035\x00" + b"\x00" * 64)
        zf.writestr("assets/leak.txt", b"api_key = 'super_secret_value_12345'")

    with patch(
        "apex.secrets_scan.dex_string_pool",
        return_value=["AKIAIOSFODNN7EXAMPLE"],
    ):
        hits = scan_apk_secrets(apk)
    sources = {item.get("source", "") for item in hits}
    assert any(s.startswith("resource-file:") for s in sources)
    assert any(s.startswith("dex-string-pool:") for s in sources)


def test_resource_only_secret_regression(tmp_path: Path) -> None:
    apk = make_apk(tmp_path / "resource.apk")
    with zipfile.ZipFile(apk, "a") as zf:
        zf.writestr("res/values/secrets.xml", b"<resources><string>api_key=leak123456789</string></resources>")
    hits = scan_apk_secrets(apk)
    assert hits
    assert any("resource-file" in item.get("source", "") for item in hits)


def test_inspect_elf_fake_so() -> None:
    # ELF64 header start (matches generate_test_apk fake .so shape)
    elf = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8 + bytes(range(48))
    report = inspect_elf(elf)
    assert report["format"] == "ELF64"


def test_scan_apk_native_libs_on_fixture(tmp_path: Path) -> None:
    apk = make_apk(tmp_path / "native.apk")
    # inject fake .so
    with zipfile.ZipFile(apk, "a") as zf:
        elf = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8 + bytes(range(48))
        zf.writestr("lib/arm64-v8a/libtest.so", elf)
    hits = scan_apk_native_libs(apk)
    assert isinstance(hits, list)
