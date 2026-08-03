"""Tests for ZIP/XAPK container resolution."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from apex.analysis import package_has_dex, resolve_android_package


@pytest.fixture(scope="module")
def sample_apk() -> Path:
    path = Path(__file__).resolve().parent / "fixtures" / "sample_test.apk"
    if not path.is_file():
        pytest.skip("sample_test.apk fixture missing")
    return path


def test_package_has_dex_on_apk(sample_apk: Path) -> None:
    assert package_has_dex(sample_apk)


def test_resolve_nested_apk_in_zip(sample_apk: Path, tmp_path: Path) -> None:
    container = tmp_path / "bundle.zip"
    with zipfile.ZipFile(container, "w") as outer:
        outer.write(sample_apk, "nested/app-release.apk")
        outer.writestr("readme.txt", "not an apk")

    resolved, meta = resolve_android_package(container, tmp_path)
    assert meta["resolved_from"] == "nested/app-release.apk"
    assert package_has_dex(resolved)
    assert "Opened" in meta["container_note"]


def test_resolve_plain_zip_without_apk(tmp_path: Path) -> None:
    plain = tmp_path / "plain.zip"
    with zipfile.ZipFile(plain, "w") as zf:
        zf.writestr("notes.txt", "hello")

    resolved, meta = resolve_android_package(plain, tmp_path)
    assert resolved == plain
    assert not package_has_dex(resolved)
    assert "No DEX" in meta["container_note"]
