"""Content-based application format detection.

APEX decides what a file *is* by reading its bytes, never by trusting its
name. Detection uses magic numbers first, then archive structure, and only
consults the file extension as a tiebreaker between structurally identical
containers. Nothing here shells out to an external tool and nothing extracts
the archive.
"""

from __future__ import annotations

import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Bounded read for magic sniffing. Every supported magic lives in the first
# few bytes; 64 bytes is generous and keeps detection O(1) on huge files.
MAGIC_READ_BYTES = 64

DEX_MAGICS = tuple(f"dex\n{version:03d}\0".encode("ascii") for version in range(35, 46))
ELF_MAGIC = b"\x7fELF"
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
MACHO_MAGICS = (
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
)
FAT_MAGICS = (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")


@dataclass(frozen=True)
class FormatInfo:
    """The detected format of an input file."""

    format: str
    platform: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    container: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "platform": self.platform,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "container": self.container,
        }


def _read_magic(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(MAGIC_READ_BYTES)


def _classify_zip(path: Path) -> FormatInfo:
    """Classify a ZIP container by the shape of its member list."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        return FormatInfo("unknown", "unknown", "none", [f"corrupt zip: {exc}"], "zip")

    name_set = set(names)
    evidence: list[str] = []

    has_ios_payload = any(
        len(parts) >= 2 and parts[0] == "Payload" and parts[1].endswith(".app")
        for parts in (name.split("/") for name in names)
    )
    if has_ios_payload:
        evidence.append("Payload/*.app/ present")
        return FormatInfo("ipa", "ios", "high", evidence, "zip")

    has_manifest = "AndroidManifest.xml" in name_set
    has_dex = any(
        Path(name).name.startswith("classes") and name.endswith(".dex") for name in names
    )
    if has_manifest and has_dex:
        evidence.append("AndroidManifest.xml + classes*.dex")
        return FormatInfo("apk", "android", "high", evidence, "zip")

    # App Bundle: module directories with a protobuf manifest.
    if "BundleConfig.pb" in name_set or "base/manifest/AndroidManifest.xml" in name_set:
        evidence.append("BundleConfig.pb or base/manifest/AndroidManifest.xml")
        return FormatInfo("aab", "android", "high", evidence, "zip")

    # APKS set produced by bundletool.
    if "toc.pb" in name_set and any(name.endswith(".apk") for name in names):
        evidence.append("toc.pb + *.apk members")
        return FormatInfo("apks", "android", "high", evidence, "zip")

    # XAPK/APKM style split bundles.
    if any(name.endswith(".apk") for name in names) and (
        "manifest.json" in name_set or "info.json" in name_set
    ):
        evidence.append("*.apk members + manifest.json")
        return FormatInfo("xapk", "android", "high", evidence, "zip")

    if has_manifest:
        evidence.append("AndroidManifest.xml without classes.dex")
        return FormatInfo("apk", "android", "medium", evidence, "zip")

    if any(name.endswith(".apk") for name in names):
        evidence.append("archive contains *.apk members")
        return FormatInfo("apks", "android", "low", evidence, "zip")

    evidence.append("zip archive with no recognized mobile layout")
    return FormatInfo("zip", "unknown", "low", evidence, "zip")


def detect_format(path: Path) -> FormatInfo:
    """Detect the format of ``path`` from its content.

    Raises ``FileNotFoundError`` if the path is not a readable file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"not a file: {path}")

    head = _read_magic(path)
    if not head:
        return FormatInfo("unknown", "unknown", "none", ["empty file"])

    if head.startswith(DEX_MAGICS):
        version = head[4:7].decode("ascii", "replace")
        return FormatInfo("dex", "android", "high", [f"dex magic, version {version}"])

    if head.startswith(ELF_MAGIC):
        return FormatInfo("elf", "android", "high", ["ELF magic"])

    if head[:4] in MACHO_MAGICS:
        return FormatInfo("macho", "ios", "high", ["Mach-O magic"])

    if head[:4] in FAT_MAGICS:
        # A fat Mach-O and a Java class file share 0xCAFEBABE; disambiguate by
        # the architecture count, which is small and sane for a real binary.
        try:
            count = struct.unpack_from(">I", head, 4)[0]
        except struct.error:
            count = 0
        if 0 < count <= 64:
            return FormatInfo("macho", "ios", "high", ["fat Mach-O magic"])
        return FormatInfo("unknown", "unknown", "low", ["0xCAFEBABE with implausible arch count"])

    if head[:4] in ZIP_MAGICS:
        return _classify_zip(path)

    return FormatInfo("unknown", "unknown", "none", ["no recognized magic"])


def is_ios_bundle(path: Path) -> bool:
    """True when the file is an iOS application archive, regardless of name."""
    try:
        return detect_format(path).format == "ipa"
    except (FileNotFoundError, OSError):
        return False


def is_android_package(path: Path) -> bool:
    """True when the file is an Android package container."""
    try:
        return detect_format(path).format in {"apk", "aab", "apks", "xapk"}
    except (FileNotFoundError, OSError):
        return False
