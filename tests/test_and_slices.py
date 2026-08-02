"""Verification tests for slices AND-01, AND-02 and AND-04.

Each test maps to a numbered verification step in the "Phase 5" section of
``docs/PROJECT_BLUEPRINT.md``.

Fixture honesty note: APEX cannot compile new DEX bytecode without the Android
SDK, so tests that need a specific *bytecode* shape (a cross-DEX call, a
``native``-declared method) drive the resolution logic with a synthetic merged
index in exactly the form ``dex_metadata`` emits. Everything on the native side
is a real compiled ELF, and the multidex packaging test uses the committed real
``classes.dex``.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from apex.analysis import ApexError, build_crossrefs, extract_apk, scan_dex_metadata
from apex.dex.unified import build_symbol_table, duplicate_classes, resolve_cross_dex
from apex.format_detect import detect_format
from apex.ios.ipa import is_ipa
from apex.jni.mangle import jni_long_name, jni_short_name, mangle
from apex.jni.xref import (
    build_jni_graph,
    detect_load_library,
    native_methods,
    resolve_java_to_symbol,
    resolve_symbol_to_java,
)
from apex.native.elf import exported_functions, parse_elf_symbols

REAL_DEX = Path("core/dex_parser/tests/fixtures/classes.dex")
SAMPLE_APK = Path("tests/fixtures/sample_test.apk")
JNI_APK = Path("tests/fixtures/jni_native.apk")
JNI_SO = Path("tests/fixtures/libapexjni.so")
TEST_CLASS = "com.apex.testapp.MainActivity"


def _ensure_sample_apk() -> Path:
    if not SAMPLE_APK.is_file():
        subprocess.run([sys.executable, "scripts/generate_test_apk.py"], check=True)
    return SAMPLE_APK


def _ensure_jni_fixture() -> tuple[Path, Path]:
    if not (JNI_APK.is_file() and JNI_SO.is_file()):
        subprocess.run([sys.executable, "scripts/generate_jni_fixture.py"], check=True)
    return JNI_APK, JNI_SO


def _build_ipa(path: Path) -> Path:
    import plistlib

    info = plistlib.dumps({"CFBundleIdentifier": "com.t.app", "CFBundleExecutable": "T"})
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Payload/T.app/Info.plist", info)
        archive.writestr("Payload/T.app/T", b"\xcf\xfa\xed\xfe" + b"\x00" * 60)
    return path


def _multidex_apk(path: Path, count: int = 3) -> Path:
    """APK carrying `count` real DEX files (copies of the committed fixture)."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"<manifest/>")
        for index in range(count):
            name = "classes.dex" if index == 0 else f"classes{index + 1}.dex"
            archive.write(REAL_DEX, name)
    return path


def _synthetic_multidex_index() -> dict:
    """A merged index shaped exactly like `dex_metadata` output, across 2 DEX."""
    return {
        "dex_files": ["classes.dex", "classes2.dex"],
        "classes": [
            {"dex": "classes.dex", "name": "com.app.Core"},
            {"dex": "classes2.dex", "name": "com.app.Feature"},
        ],
        "methods": [
            {
                "dex": "classes.dex",
                "class": "com.app.Core",
                "name": "handle",
                "descriptor": "(I)V",
                "access": "public",
            },
            {
                "dex": "classes2.dex",
                "class": "com.app.Feature",
                "name": "run",
                "descriptor": "()V",
                "access": "public",
            },
        ],
        "edges": [
            # cross-DEX: Feature (classes2.dex) calls Core (classes.dex)
            {
                "caller_class": "com.app.Feature",
                "caller_method": "run",
                "callee": "com.app.Core::handle(I)V",
                "offset": 4,
            },
            # external: framework call that is genuinely not in this package
            {
                "caller_class": "com.app.Core",
                "caller_method": "handle",
                "callee": "android.util.Log::d(Ljava/lang/String;)I",
                "offset": 2,
            },
        ],
    }


# ---------------------------------------------------------------- AND-02


def test_and02_all_formats_detected_regardless_of_name(tmp_path: Path):
    """Step 1: correct detection with wrong and missing extensions."""
    apk = _ensure_sample_apk()
    _, so = _ensure_jni_fixture()
    ipa = _build_ipa(tmp_path / "real.ipa")
    dex = tmp_path / "real.dex"
    dex.write_bytes(REAL_DEX.read_bytes())

    truth = {apk: "apk", ipa: "ipa", dex: "dex", so: "elf"}
    for source, expected in truth.items():
        assert detect_format(source).format == expected, source
        for alias in (f"wrong{Path(source).suffix or '.bin'}", "noext"):
            renamed = tmp_path / f"{expected}_{alias}"
            shutil.copy(source, renamed)
            assert detect_format(renamed).format == expected, renamed


def test_and02_renamed_ipa_routes_to_ios(tmp_path: Path):
    """Step 2: an IPA named .apk is still an iOS bundle."""
    ipa = _build_ipa(tmp_path / "app.ipa")
    disguised = tmp_path / "app.apk"
    shutil.copy(ipa, disguised)
    assert detect_format(disguised).format == "ipa"
    assert is_ipa(disguised) is True

    apk = _ensure_sample_apk()
    reverse = tmp_path / "android.ipa"
    shutil.copy(apk, reverse)
    assert is_ipa(reverse) is False


def test_and02_unsupported_input_is_actionable(tmp_path: Path):
    """Step 3: unsupported/corrupt input names the detected type, no partial report."""
    junk = tmp_path / "notes.txt"
    junk.write_bytes(b"just some text, definitely not an app")
    detected = detect_format(junk)
    assert detected.format == "unknown"
    assert detected.evidence

    from apex.web import ApexWebHandler

    handler = ApexWebHandler.__new__(ApexWebHandler)
    with pytest.raises(ApexError) as excinfo:
        ApexWebHandler._analyze_path(handler, junk)
    assert "unknown" in str(excinfo.value)


def test_and02_detection_is_bounded_and_non_extracting(tmp_path: Path):
    """Step 4: detection reads a bounded prefix and never extracts."""
    from apex.format_detect import MAGIC_READ_BYTES

    assert MAGIC_READ_BYTES <= 256
    dex = tmp_path / "bare.dex"
    dex.write_bytes(REAL_DEX.read_bytes())
    before = set(tmp_path.iterdir())
    assert detect_format(dex).format == "dex"
    assert set(tmp_path.iterdir()) == before

    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "does-not-exist")


# ---------------------------------------------------------------- AND-01


def test_and01_multidex_package_merges_every_dex(tmp_path: Path):
    """Step 1: all DEX files in a 3-DEX package are parsed into one index."""
    apk = _multidex_apk(tmp_path / "multi.apk", count=3)
    extract_dir, _ = extract_apk(apk, tmp_path / "work")
    index = scan_dex_metadata(extract_dir)
    assert index["dex_files"] == ["classes.dex", "classes2.dex", "classes3.dex"]
    seen = {cls["dex"] for cls in index["classes"]}
    assert seen == {"classes.dex", "classes2.dex", "classes3.dex"}
    assert index["cross_dex"]["symbol_count"] > 0


def test_and01_cross_dex_call_resolves_as_live_edge():
    """Step 2: a classes2 -> classes call resolves, not a synthesized stub."""
    resolved = resolve_cross_dex(_synthetic_multidex_index())
    cross = [edge for edge in resolved["edges"] if edge["cross_dex"]]
    assert len(cross) == 1
    edge = cross[0]
    assert edge["resolved"] is True
    assert edge["caller_dex"] == "classes2.dex"
    assert edge["callee_dex"] == "classes.dex"
    assert resolved["cross_dex_edges"] == 1

    graph = build_crossrefs({**_synthetic_multidex_index(), "edges": resolved["edges"]})
    target = next(n for n in graph["nodes"] if n["id"] == "com.app.Core::handle(I)V")
    assert target["kind"] == "method"
    external = next(
        n for n in graph["nodes"] if n["id"].startswith("android.util.Log")
    )
    assert external["kind"] == "external"


def test_and01_no_method_ceiling_beyond_64k():
    """Step 3: combined method count above 65,536 resolves with no ceiling error."""
    total = 70_000
    methods = [
        {
            "dex": "classes.dex" if i % 2 == 0 else "classes2.dex",
            "class": f"com.app.C{i}",
            "name": "m",
            "descriptor": "()V",
            "access": "public",
        }
        for i in range(total)
    ]
    classes = [
        {"dex": method["dex"], "name": method["class"]} for method in methods
    ]
    edges = [
        {
            "caller_class": "com.app.C1",
            "caller_method": "m",
            "callee": "com.app.C0::m()V",
            "offset": 0,
        }
    ]
    resolved = resolve_cross_dex(
        {"classes": classes, "methods": methods, "edges": edges}
    )
    assert resolved["symbol_count"] == total
    assert resolved["cross_dex_edges"] == 1
    assert resolved["unresolved_edges"] == 0


def test_and01_duplicate_classes_and_unresolved_reasons():
    """Step 4 support: duplicates surfaced; external calls state a reason."""
    index = _synthetic_multidex_index()
    index["classes"].append({"dex": "classes2.dex", "name": "com.app.Core"})
    assert duplicate_classes(index) == [
        {"class": "com.app.Core", "dex_files": ["classes.dex", "classes2.dex"]}
    ]

    resolved = resolve_cross_dex(_synthetic_multidex_index())
    unresolved = [edge for edge in resolved["edges"] if not edge["resolved"]]
    assert len(unresolved) == 1
    assert unresolved[0]["unresolved_reason"]

    table = build_symbol_table(_synthetic_multidex_index())
    assert "com.app.Core::handle(I)V" in table
    assert table["com.app.Core::handle(I)V"].dex == "classes.dex"


# ---------------------------------------------------------------- AND-04


def test_and04_elf_parser_reads_real_shared_object():
    """APEX parses a real ELF itself, with no external tool."""
    _, so = _ensure_jni_fixture()
    parsed = parse_elf_symbols(so.read_bytes())
    assert parsed["valid"] is True
    assert parsed["class"] == 64
    assert parsed["endian"] == "little"
    assert parsed["symbol_count"] > 0
    exports = exported_functions(so.read_bytes())
    assert "Java_com_apex_testapp_MainActivity_nativeInit" in exports
    assert "helper_not_exported" not in exports


def test_and04_elf_parser_rejects_non_elf():
    """Step 5 support: non-ELF and truncated input degrade explicitly."""
    assert parse_elf_symbols(b"not an elf")["valid"] is False
    assert exported_functions(b"\x7fELF" + b"\x00" * 8) == set()
    header = bytearray(b"\x7fELF" + b"\x00" * 60)
    header[4] = 9  # invalid class
    assert parse_elf_symbols(bytes(header))["valid"] is False


def test_and04_jni_mangling_rules():
    """Step 3: _1, _3, unicode escapes and the __ overload suffix."""
    assert jni_short_name("com.example.Foo", "bar") == "Java_com_example_Foo_bar"
    assert jni_short_name("com.example.Foo", "a_b") == "Java_com_example_Foo_a_1b"
    assert jni_long_name("com.example.Foo", "f", "(I)V") == "Java_com_example_Foo_f__I"
    assert (
        jni_long_name("com.example.Foo", "f", "(Ljava/lang/String;)V")
        == "Java_com_example_Foo_f__Ljava_lang_String_2"
    )
    assert jni_long_name("com.example.Foo", "f", "([I)V") == "Java_com_example_Foo_f___3I"
    assert mangle("caf\u00e9") == "caf_000e9"


def _jni_dex_index() -> dict:
    return {
        "methods": [
            {
                "class": TEST_CLASS,
                "name": "nativeInit",
                "descriptor": "()I",
                "access": "public native",
                "dex": "classes.dex",
            },
            {
                "class": TEST_CLASS,
                "name": "nativeSum",
                "descriptor": "(II)I",
                "access": "public native",
                "dex": "classes.dex",
            },
            {
                "class": TEST_CLASS,
                "name": "native_under",
                "descriptor": "()I",
                "access": "public native",
                "dex": "classes.dex",
            },
            {
                "class": TEST_CLASS,
                "name": "notNative",
                "descriptor": "()V",
                "access": "public",
                "dex": "classes.dex",
            },
        ],
        "edges": [
            {
                "caller_class": TEST_CLASS,
                "caller_method": "onCreate",
                "callee": "java.lang.System::loadLibrary(Ljava/lang/String;)V",
            }
        ],
    }


def test_and04_native_methods_resolve_and_are_bidirectional(tmp_path: Path):
    """Steps 1 and 2: automatic resolution, both directions, no manual step."""
    _, so = _ensure_jni_fixture()
    lib_dir = tmp_path / "lib" / "arm64-v8a"
    lib_dir.mkdir(parents=True)
    shutil.copy(so, lib_dir / "libapexjni.so")
    native_index = {
        "native_libs": [{"path": "lib/arm64-v8a/libapexjni.so", "abi": "arm64-v8a"}]
    }
    index = _jni_dex_index()
    graph = build_jni_graph(index, native_index, tmp_path)

    assert graph["native_method_count"] == 3  # notNative excluded
    assert graph["resolved_count"] == 3
    assert graph["unresolved_count"] == 0
    symbols = {edge["symbol"] for edge in graph["edges"]}
    assert symbols == {
        "Java_com_apex_testapp_MainActivity_nativeInit",
        "Java_com_apex_testapp_MainActivity_nativeSum__II",
        "Java_com_apex_testapp_MainActivity_native_1under",
    }

    forward = resolve_java_to_symbol(graph, f"{TEST_CLASS}::nativeSum(II)I")
    assert forward == ["Java_com_apex_testapp_MainActivity_nativeSum__II"]
    reverse = resolve_symbol_to_java(
        graph, "Java_com_apex_testapp_MainActivity_nativeSum__II"
    )
    assert reverse == [f"{TEST_CLASS}::nativeSum(II)I"]

    assert detect_load_library(index)["count"] == 1
    assert native_methods(index)[0]["name"] == "nativeInit"


def test_and04_unresolved_reports_reason_not_a_guess(tmp_path: Path):
    """Step 4: a native method with no export is reported, never invented."""
    _, so = _ensure_jni_fixture()
    lib_dir = tmp_path / "lib" / "arm64-v8a"
    lib_dir.mkdir(parents=True)
    shutil.copy(so, lib_dir / "libapexjni.so")
    index = _jni_dex_index()
    index["methods"].append(
        {
            "class": TEST_CLASS,
            "name": "absent",
            "descriptor": "()V",
            "access": "public native",
            "dex": "classes.dex",
        }
    )
    graph = build_jni_graph(
        index,
        {"native_libs": [{"path": "lib/arm64-v8a/libapexjni.so", "abi": "arm64-v8a"}]},
        tmp_path,
    )
    assert graph["unresolved_count"] == 1
    unresolved = graph["unresolved"][0]
    assert unresolved["java"] == f"{TEST_CLASS}::absent()V"
    assert unresolved["resolved"] is False
    assert "RegisterNatives" in unresolved["reason"]
    assert graph["dynamic_registration_suspected"] is True


def test_and04_missing_library_degrades_explicitly(tmp_path: Path):
    """Step 5: an unreadable or non-ELF library is reported, not silently skipped."""
    (tmp_path / "lib" / "arm64-v8a").mkdir(parents=True)
    (tmp_path / "lib" / "arm64-v8a" / "libbogus.so").write_bytes(b"not elf at all")
    graph = build_jni_graph(
        _jni_dex_index(),
        {"native_libs": [{"path": "lib/arm64-v8a/libbogus.so", "abi": "arm64-v8a"}]},
        tmp_path,
    )
    assert graph["libraries"][0]["symbol_count"] == 0
    assert graph["libraries"][0]["error"]
    assert graph["unresolved_count"] == 3
    assert all("no matching export" in item["reason"] for item in graph["unresolved"])


def test_and04_wired_into_analysis_report(tmp_path: Path):
    """Interface parity: the JNI graph is part of the standard analyze report."""
    from apex.workflows import analyze_apk, jni_report

    apk, _ = _ensure_jni_fixture()
    report = analyze_apk(apk, tmp_path / "out")
    assert "jni" in report["native"]
    assert report["native"]["jni"]["libraries"], "bundled .so should be summarized"
    standalone = jni_report(apk, tmp_path / "jni-work")
    assert standalone["apk"].endswith("jni_native.apk")


def test_and04_elf_symbol_struct_shapes():
    """32-bit and big-endian headers are accepted by the class/data checks."""
    for ei_class, ei_data in ((1, 1), (2, 1), (1, 2), (2, 2)):
        header = bytearray(b"\x7fELF" + b"\x00" * 60)
        header[4] = ei_class
        header[5] = ei_data
        parsed = parse_elf_symbols(bytes(header))
        assert parsed["valid"] is True
        assert parsed["class"] == (64 if ei_class == 2 else 32)


def test_and04_fat_macho_not_confused_with_elf(tmp_path: Path):
    """Format guard: a fat Mach-O is not mistaken for an Android library."""
    fat = tmp_path / "fat.bin"
    fat.write_bytes(b"\xca\xfe\xba\xbe" + struct.pack(">I", 2) + b"\x00" * 56)
    assert detect_format(fat).format == "macho"
