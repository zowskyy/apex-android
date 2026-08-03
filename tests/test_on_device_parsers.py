"""On-device parser fallbacks (lightweight DEX, apkInspector manifest)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from apex.analysis import (
    _manifest_summary,
    dex_metadata,
    normalize_uploaded_package,
    resolve_android_package,
)
from apex.device_profile import configure_device_profile


@pytest.fixture(scope="module")
def sample_apk() -> Path:
    path = Path(__file__).resolve().parent / "fixtures" / "sample_test.apk"
    if not path.is_file():
        pytest.skip("sample_test.apk fixture missing")
    return path


@pytest.fixture
def on_device_profile():
    configure_device_profile(ram_mb=4096, cpu_cores=4, engine_mode="on_device")
    yield
    configure_device_profile(engine_mode="desktop")


def test_lightweight_dex_metadata_on_sample(sample_apk: Path, on_device_profile) -> None:
    with zipfile.ZipFile(sample_apk) as archive:
        raw = archive.read("classes.dex")
    meta = dex_metadata(raw, "classes.dex", lightweight=True)
    assert meta.get("lightweight")
    assert "classes" in meta


def test_lightweight_dex_on_release_apk_if_present(on_device_profile) -> None:
    apk = Path("/tmp/APEX-Mobile-0.4.7.apk")
    if not apk.is_file():
        pytest.skip("release APK not on disk")
    with zipfile.ZipFile(apk) as archive:
        meta = dex_metadata(archive.read("classes.dex"), "classes.dex", lightweight=True)
    assert len(meta.get("classes") or []) > 1000


def test_manifest_apkinspector_smoke_bytes(on_device_profile) -> None:
    raw = Path("apex/data/smoke_manifest.bin").read_bytes()
    summary = _manifest_summary(raw)
    assert summary.get("package") == "io.apex.standalone"


def test_normalize_uploaded_package_adds_zip_suffix(tmp_path: Path, sample_apk: Path) -> None:
    bare = tmp_path / "picked-from-phone"
    bare.write_bytes(sample_apk.read_bytes())
    normalized = normalize_uploaded_package(bare)
    assert normalized.suffix.lower() == ".zip"
    assert normalized.is_file()


def test_resolve_extensionless_release_zip(sample_apk: Path, tmp_path: Path) -> None:
    container = tmp_path / "APEX-Mobile-test-android"
    with zipfile.ZipFile(container, "w") as outer:
        outer.write(sample_apk, "APEX-Mobile-test.apk")
        outer.writestr("INSTALL.txt", "notes")
    resolved, meta = resolve_android_package(container, tmp_path)
    assert meta["resolved_from"] == "APEX-Mobile-test.apk"
    assert resolved.name.startswith(".resolved-")


def test_engine_validate_passes() -> None:
    from apex.engine_validate import validate_on_device_parsers

    result = validate_on_device_parsers()
    assert result["ok"] == "true"
    assert result.get("package") == "io.apex.standalone"
