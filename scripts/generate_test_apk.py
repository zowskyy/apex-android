"""Generate a synthetic-but-realistic APK fixture for testing APEX.

This is deliberately NOT a real downloaded third-party APK — it's built
locally so the fixture is deterministic, reproducible, and license-free.
It mimics real APK internal structure and scale (entry count, size,
directory layout) closely enough to be a meaningful stand-in for the
F-Droid/NewPipe corpus referenced in docs/PROJECT_STATE.md, which is not
checked into this repo.

Usage:
    python scripts/generate_test_apk.py [output_path] [--clean]
        --clean   also write a companion malicious variant for CVE testing
"""
from __future__ import annotations

import argparse
import random
import struct
import zipfile
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_test.apk"

MANIFEST_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.apex.testfixture" android:versionCode="1" android:versionName="1.0">
    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="34"/>
    <application android:label="APEX Test Fixture" android:icon="@drawable/icon_0000">
        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <service android:name=".BackgroundService"/>
        <receiver android:name=".BootReceiver"/>
    </application>
</manifest>
"""

LAYOUT_XML_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:orientation="vertical" android:layout_width="match_parent" android:layout_height="match_parent">
    <TextView android:id="@+id/label_{i}" android:text="Screen {i}"
        android:layout_width="wrap_content" android:layout_height="wrap_content"/>
</LinearLayout>
"""


def _fake_dex(seed: int) -> bytes:
    # Real DEX magic ("dex\n035\0") + checksum/signature-shaped padding so a
    # header sniff sees a plausible DEX, without implementing the real format.
    rng = random.Random(seed)
    magic = b"dex\n035\x00"
    checksum = struct.pack("<I", rng.getrandbits(32))
    signature = bytes(rng.getrandbits(8) for _ in range(20))
    body = bytes(rng.getrandbits(8) for _ in range(64 * 1024))
    return magic + checksum + signature + body


def _fake_arsc(seed: int) -> bytes:
    # Real resources.arsc chunk header (RES_TABLE_TYPE = 0x0002) followed by
    # a minimal ResStringPool chunk header (type 0x0001), enough to look like
    # a real arsc to a chunk-scanning tool without a full string pool.
    rng = random.Random(seed)
    table_header = struct.pack("<HHI", 0x0002, 12, 12 + 4096)
    package_count = struct.pack("<I", 1)
    pool_header = struct.pack("<HHI", 0x0001, 28, 28)
    pool_fields = struct.pack("<IIIII", 0, 0, 0, 28, 0)
    padding = bytes(rng.getrandbits(8) for _ in range(4096 - len(pool_header) - len(pool_fields)))
    return table_header + package_count + pool_header + pool_fields + padding


def _fake_so(seed: int, size: int) -> bytes:
    rng = random.Random(seed)
    elf_magic = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8  # ELF64 header start
    return elf_magic + bytes(rng.getrandbits(8) for _ in range(size - len(elf_magic)))


def build_apk(out_path: Path, n_drawables: int = 900, n_layouts: int = 120, n_strings_files: int = 20) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("AndroidManifest.xml", MANIFEST_XML)
        zf.writestr("resources.arsc", _fake_arsc(1))
        zf.writestr("classes.dex", _fake_dex(2))
        zf.writestr("classes2.dex", _fake_dex(3))

        for i in range(n_layouts):
            zf.writestr(f"res/layout/screen_{i:04d}.xml", LAYOUT_XML_TEMPLATE.format(i=i).encode("utf-8"))

        for i in range(n_drawables):
            # PNG magic + random bytes, representative size for a small icon/drawable.
            png = b"\x89PNG\r\n\x1a\n" + bytes(rng.getrandbits(8) for _ in range(rng.randint(2_000, 12_000)))
            zf.writestr(f"res/drawable/icon_{i:04d}.png", png)

        for i in range(n_strings_files):
            zf.writestr(f"res/values-{['en', 'fr', 'de', 'es', 'ja'][i % 5]}-v{i}/strings.xml",
                        f"<resources><string name=\"app_name\">Fixture {i}</string></resources>".encode())

        for abi in ("arm64-v8a", "armeabi-v7a", "x86_64"):
            zf.writestr(f"lib/{abi}/libapex_test.so", _fake_so(hash(abi) & 0xFFFF, 512 * 1024))

        for i in range(30):
            zf.writestr(f"assets/data/chunk_{i:03d}.bin", bytes(rng.getrandbits(8) for _ in range(50_000)))

        zf.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\nCreated-By: apex-test-fixture\n")
        zf.writestr("META-INF/CERT.SF", b"Signature-Version: 1.0\n")
        zf.writestr("META-INF/CERT.RSA", bytes(rng.getrandbits(8) for _ in range(1024)))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    with zipfile.ZipFile(out_path) as zf:
        n_entries = len(zf.infolist())
    print(f"Wrote {out_path} ({size_mb:.1f} MB, {n_entries} entries)")


def build_malicious_variant(out_path: Path) -> None:
    """Companion fixture reconstructing the CVE-2026-39973 traversal pattern
    inside an otherwise-normal-looking APK, for end-to-end security testing."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("AndroidManifest.xml", MANIFEST_XML)
        zf.writestr("resources.arsc", _fake_arsc(1))
        zf.writestr("classes.dex", _fake_dex(2))
        zf.writestr("res/layout/screen_0000.xml", LAYOUT_XML_TEMPLATE.format(i=0).encode())
        zf.writestr("../../../../tmp/apex_cve_traversal_marker", b"PWNED")
        zf.writestr("..\\..\\..\\apex_cve_traversal_marker_win", b"PWNED")
        zf.writestr("/etc/apex_cve_traversal_marker_abs", b"PWNED")
    print(f"Wrote {out_path} (malicious traversal variant)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--clean", action="store_true", help="also write a malicious traversal-variant fixture")
    args = parser.parse_args()

    build_apk(args.output)
    if args.clean:
        build_malicious_variant(args.output.with_name(args.output.stem + "_malicious" + args.output.suffix))
