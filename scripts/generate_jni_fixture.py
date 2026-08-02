#!/usr/bin/env python3
"""Build a deterministic native-library fixture for the JNI cross-reference tests.

Compiles a small shared object exporting real JNI-mangled symbols, then packages
it into an APK-shaped archive alongside the committed real ``classes.dex``.
Requires only a C compiler; no Android SDK, device, or network access.

Usage:
    python scripts/generate_jni_fixture.py [--clean]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parent))
REAL_DEX = ROOT / "core" / "dex_parser" / "tests" / "fixtures" / "classes.dex"

# Exports both JNI spellings: the short form and an overload-qualified long
# form, plus JNI_OnLoad so the dynamic-registration path is exercised too.
SOURCE = """
#include <stdint.h>

int Java_com_apex_testapp_MainActivity_nativeInit(void *env, void *clazz) {
    return 1;
}

int Java_com_apex_testapp_MainActivity_nativeSum__II(void *env, void *clazz,
                                                     int a, int b) {
    return a + b;
}

int Java_com_apex_testapp_MainActivity_native_1under(void *env, void *clazz) {
    return 2;
}

int JNI_OnLoad(void *vm, void *reserved) {
    return 0x00010006;
}

static int helper_not_exported(void) { return 42; }
"""


def build_shared_object(destination: Path) -> Path:
    compiler = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
    if not compiler:
        raise SystemExit("a C compiler (gcc/cc/clang) is required to build this fixture")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "apexjni.c"
        source.write_text(SOURCE, encoding="utf-8")
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [compiler, "-shared", "-fPIC", "-o", str(destination), str(source)],
            check=True,
        )
    return destination


def build_apk(so_path: Path, apk_path: Path) -> Path:
    if not REAL_DEX.is_file():
        raise SystemExit(f"missing real DEX fixture: {REAL_DEX}")
    apk_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"<manifest/>")
        archive.write(REAL_DEX, "classes.dex")
        archive.write(so_path, "lib/arm64-v8a/libapexjni.so")
    return apk_path


def build_resolvable_apk(so_path: Path, apk_path: Path) -> Path:
    """APK whose DEX declares `native` methods matching the library exports.

    Uses the assembled DEX from ``generate_exception_dex.py``, which contains a
    ``com.apex.testapp.MainActivity`` class with real ``native`` method
    declarations, so JNI resolution can be verified end to end.
    """
    from generate_exception_dex import build_dex

    apk_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"<manifest/>")
        archive.writestr("classes.dex", build_dex())
        archive.write(so_path, "lib/arm64-v8a/libapexjni.so")
    return apk_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="rebuild even if present")
    args = parser.parse_args()

    apk = FIXTURES / "jni_native.apk"
    resolvable = FIXTURES / "jni_resolvable.apk"
    so = FIXTURES / "libapexjni.so"
    if apk.is_file() and so.is_file() and resolvable.is_file() and not args.clean:
        print(f"fixture already present: {apk}")
        return 0
    build_shared_object(so)
    build_apk(so, apk)
    build_resolvable_apk(so, resolvable)
    print(f"Wrote {so}, {apk} and {resolvable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
