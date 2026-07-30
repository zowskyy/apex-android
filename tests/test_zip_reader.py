from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

import pytest

import apex

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_test_apk  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def realistic_apk() -> Path:
    """Synthetic-but-realistic APK (~9MB, ~1000 entries, APK-shaped directory
    layout) generated on demand — see scripts/generate_test_apk.py for why
    this is used instead of a downloaded third-party APK."""
    path = FIXTURES_DIR / "sample_test.apk"
    if not path.exists():
        generate_test_apk.build_apk(path)
    return path


def _write_malicious_zip(path: Path) -> None:
    """Reconstruction of the CVE-2026-39973 apktool path-traversal pattern:
    entry names using ../ segments (and OS-specific variants) to escape the
    extraction directory."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"<manifest/>")
        zf.writestr("res/layout/main.xml", b"<LinearLayout/>")
        zf.writestr("../../../../tmp/apex_cve_traversal_marker", b"PWNED")
        zf.writestr("..\\..\\..\\apex_cve_traversal_marker_win", b"PWNED")
        zf.writestr("/etc/apex_cve_traversal_marker_abs", b"PWNED")


def test_cve_2026_39973_traversal_blocked(tmp_path: Path):
    apk = tmp_path / "malicious.apk"
    work_dir = tmp_path / "work"
    _write_malicious_zip(apk)

    extract_dir, report = apex.extract_apk(apk, work_dir)

    assert report["warned"] >= 3
    assert report["extracted"] == 2  # only the two clean entries

    # The critical assertion: nothing escaped extract_dir onto the real filesystem.
    assert not (tmp_path.parent / "apex_cve_traversal_marker").exists()
    assert not Path("/tmp/apex_cve_traversal_marker").exists()

    extracted_files = sorted(p.relative_to(extract_dir).as_posix() for p in extract_dir.rglob("*") if p.is_file())
    assert extracted_files == ["AndroidManifest.xml", "res/layout/main.xml"]

    warn_names = {e["name"] for e in report["entries"] if e["verdict"] == "WARN"}
    assert "../../../../tmp/apex_cve_traversal_marker" in warn_names


@pytest.mark.skipif(apex._native_zip is None, reason="apex_zip_reader native extension not installed")
def test_extract_benchmark_vs_python_zipfile(realistic_apk: Path, tmp_path: Path):
    """Not the real F-Droid/NewPipe corpus (not present in this checkout —
    see scripts/generate_test_apk.py), but a same-scale substitute (~9MB,
    ~1000 entries, real APK directory layout). Guards against a regression
    where the native path becomes dramatically slower than zipfile; does not
    by itself prove the blueprint's 10x target.
    """
    py_dir = tmp_path / "py_extract"
    t0 = time.perf_counter()
    with zipfile.ZipFile(realistic_apk, "r") as zf:
        zf.extractall(py_dir)
    python_elapsed = time.perf_counter() - t0

    rust_dir = tmp_path / "rust_extract"
    t0 = time.perf_counter()
    apex.extract_apk(realistic_apk, rust_dir.parent / "rust_work")
    rust_elapsed = time.perf_counter() - t0

    assert rust_elapsed <= python_elapsed * 2.0, (
        f"native extract ({rust_elapsed:.4f}s) unexpectedly much slower than "
        f"zipfile ({python_elapsed:.4f}s)"
    )


def test_realistic_apk_extracts_fully_clean(realistic_apk: Path, tmp_path: Path):
    extract_dir, report = apex.extract_apk(realistic_apk, tmp_path / "work")
    assert report["warned"] == 0
    assert report["extracted"] == report["total_entries"] == 1080
    assert (extract_dir / "AndroidManifest.xml").exists()
    assert (extract_dir / "classes.dex").exists()
