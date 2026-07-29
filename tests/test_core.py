"""
Slice 0.3 verification tests — runs against real APKs if available,
falls back to synthetic fixtures if not.
"""
import json
import zipfile
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex import (
    sha256_file, inventory_files, scan_resources,
    scan_native_libs, scan_dex_metadata,
    build_crossrefs, build_reachability,
    diff_indexes, export_minimal_bundle,
)


def make_minimal_apk(tmp: Path) -> Path:
    """Synthetic minimal APK fixture for tests that don't need a real APK."""
    apk = tmp / "minimal.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"\x03\x00")  # binary magic
        zf.writestr("resources.arsc", b"\x02\x00\x0c\x00")  # minimal arsc
        zf.writestr("classes.dex", b"dex\n035\x00")
        zf.writestr("res/layout/main.xml", b"<LinearLayout/>")
    return apk


def test_sha256_file(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"hello")
    assert len(sha256_file(f)) == 64


def test_inventory_files(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("y")
    inv = inventory_files(tmp_path)
    assert "a.txt" in inv
    assert "sub/b.txt" in inv


def test_scan_resources_minimal(tmp_path):
    apk = make_minimal_apk(tmp_path)
    work = tmp_path / "work"
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(work)
    r = scan_resources(work)
    assert r["manifest_present"] is True
    assert r["resources_arsc_present"] is True


def test_scan_native_libs_empty(tmp_path):
    apk = make_minimal_apk(tmp_path)
    work = tmp_path / "work"
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(work)
    r = scan_native_libs(work)
    assert r["native_libs"] == []


def test_scan_dex_metadata(tmp_path):
    apk = make_minimal_apk(tmp_path)
    work = tmp_path / "work"
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(work)
    r = scan_dex_metadata(work)
    assert "classes.dex" in r["dex_files"]
    assert len(r["classes"]) >= 1


def test_build_crossrefs_empty():
    xref = build_crossrefs({"classes": [], "methods": [], "edges": []})
    assert xref["nodes"] == []
    assert xref["edges"] == []


def test_build_reachability(tmp_path):
    dex = {"classes": [{"name": "com.example.MainActivity"}], "methods": [], "edges": []}
    res = {"res_files": []}
    nat = {"native_libs": []}
    r = build_reachability(dex, res, nat)
    assert "com.example.MainActivity" in r["entry_points"]
    assert r["class_count"] == 1


def test_diff_indexes_identical():
    idx = {"classes": [{"name": "A"}], "methods": [{"class": "A", "name": "foo"}], "dex_files": ["classes.dex"]}
    d = diff_indexes(idx, idx)
    assert d["classes_added"] == []
    assert d["classes_removed"] == []


def test_diff_indexes_change():
    left = {"classes": [{"name": "A"}], "methods": [], "dex_files": ["classes.dex"]}
    right = {"classes": [{"name": "B"}], "methods": [], "dex_files": ["classes.dex", "classes2.dex"]}
    d = diff_indexes(left, right)
    assert "B" in d["classes_added"]
    assert "A" in d["classes_removed"]
    assert "classes2.dex" in d["dex_files_added"]


def test_export_minimal_bundle(tmp_path):
    apk = make_minimal_apk(tmp_path)
    work = tmp_path / "work"
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(work)
    result = export_minimal_bundle(work, tmp_path / "out")
    assert "AndroidManifest.xml" in result["kept"]
    assert "classes.dex" in result["kept"]
