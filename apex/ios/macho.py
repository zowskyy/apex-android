"""A bounded Mach-O parser for iOS binary hardening analysis.

Parses thin and fat (universal) Mach-O binaries to report architecture,
position-independence (PIE), FairPlay encryption, linked dylibs/frameworks,
and hardening heuristics (stack canary, ARC, code signature). It never
executes the binary and validates every offset before reading.
"""

from __future__ import annotations

import struct
from typing import Any

MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_64 = 0xCAFEBABF
FAT_CIGAM_64 = 0xBFBAFECA

MH_PIE = 0x200000

LC_LOAD_DYLIB = 0x0C
LC_LOAD_WEAK_DYLIB = 0x18
LC_REEXPORT_DYLIB = 0x1F
LC_ENCRYPTION_INFO = 0x21
LC_ENCRYPTION_INFO_64 = 0x2C
LC_CODE_SIGNATURE = 0x1D

_CPU_ARCH_ABI64 = 0x01000000
_CPU_NAMES = {
    0x0000000C: "arm",
    0x0100000C: "arm64",
    0x00000007: "x86",
    0x01000007: "x86_64",
}


def _cpu_name(cputype: int) -> str:
    return _CPU_NAMES.get(cputype & 0xFFFFFFFF, f"cpu-0x{cputype & 0xFFFFFFFF:x}")


def _is_macho_magic(magic: int) -> bool:
    return magic in (MH_MAGIC, MH_CIGAM, MH_MAGIC_64, MH_CIGAM_64)


def _parse_thin(data: bytes, base: int) -> dict[str, Any] | None:
    if base + 4 > len(data):
        return None
    magic = struct.unpack_from(">I", data, base)[0]
    if magic in (MH_MAGIC, MH_MAGIC_64):
        endian = ">"
    elif magic in (MH_CIGAM, MH_CIGAM_64):
        endian = "<"
    else:
        return None
    magic_native = struct.unpack_from(endian + "I", data, base)[0]
    is64 = magic_native in (MH_MAGIC_64, MH_CIGAM_64)
    header_size = 32 if is64 else 28
    if base + header_size > len(data):
        return None
    cputype, _cpusub, _filetype, ncmds, _sizeofcmds, flags = struct.unpack_from(
        endian + "iiIIII", data, base + 4
    )
    result: dict[str, Any] = {
        "arch": _cpu_name(cputype),
        "is_64_bit": is64,
        "pie": bool(flags & MH_PIE),
        "encrypted": False,
        "has_code_signature": False,
        "dylibs": [],
    }
    offset = base + header_size
    ncmds = min(ncmds, 10000)
    for _ in range(ncmds):
        if offset + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from(endian + "II", data, offset)
        if cmdsize < 8 or offset + cmdsize > len(data):
            break
        if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB):
            name_off = struct.unpack_from(endian + "I", data, offset + 8)[0]
            if 8 <= name_off < cmdsize:
                raw = data[offset + name_off : offset + cmdsize]
                name = raw.split(b"\0", 1)[0].decode("utf-8", "replace")
                if name:
                    result["dylibs"].append(name)
        elif cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64):
            if offset + 20 <= len(data):
                cryptid = struct.unpack_from(endian + "I", data, offset + 16)[0]
                result["encrypted"] = cryptid != 0
        elif cmd == LC_CODE_SIGNATURE:
            result["has_code_signature"] = True
        offset += cmdsize

    slice_end = len(data)
    body = data[base:slice_end]
    result["has_stack_canary"] = (
        b"__stack_chk_guard" in body or b"__stack_chk_fail" in body
    )
    result["has_arc"] = b"_objc_release" in body or b"_objc_storeStrong" in body
    result["frameworks"] = sorted(_frameworks_from_dylibs(result["dylibs"]))
    return result


def _frameworks_from_dylibs(dylibs: list[str]) -> set[str]:
    frameworks: set[str] = set()
    for path in dylibs:
        # e.g. @rpath/GoogleMobileAds.framework/GoogleMobileAds
        if ".framework/" in path:
            name = path.split(".framework/", 1)[0].rsplit("/", 1)[-1]
            if name:
                frameworks.add(name)
    return frameworks


def parse_macho(data: bytes) -> dict[str, Any]:
    """Parse a Mach-O (thin or fat) binary into a hardening summary."""
    if len(data) < 8:
        return {"valid": False, "error": "file too small to be Mach-O", "architectures": []}

    magic_be = struct.unpack_from(">I", data, 0)[0]
    arches: list[dict[str, Any]] = []

    if magic_be in (FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_64, FAT_CIGAM_64):
        is64 = magic_be in (FAT_MAGIC_64, FAT_CIGAM_64)
        nfat = struct.unpack_from(">I", data, 4)[0]
        nfat = min(nfat, 64)
        entry_size = 32 if is64 else 20
        cursor = 8
        for _ in range(nfat):
            if cursor + entry_size > len(data):
                break
            if is64:
                offset = struct.unpack_from(">Q", data, cursor + 8)[0]
            else:
                offset = struct.unpack_from(">I", data, cursor + 8)[0]
            parsed = _parse_thin(data, offset)
            if parsed:
                arches.append(parsed)
            cursor += entry_size
    elif _is_macho_magic(magic_be) or _is_macho_magic(
        struct.unpack_from("<I", data, 0)[0]
    ):
        parsed = _parse_thin(data, 0)
        if parsed:
            arches.append(parsed)
    else:
        return {"valid": False, "error": "not a Mach-O binary", "architectures": []}

    all_dylibs = sorted({lib for arch in arches for lib in arch.get("dylibs", [])})
    all_frameworks = sorted({fw for arch in arches for fw in arch.get("frameworks", [])})
    return {
        "valid": bool(arches),
        "fat": magic_be in (FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_64, FAT_CIGAM_64),
        "architectures": arches,
        "dylibs": all_dylibs,
        "frameworks": all_frameworks,
        "pie": all(a.get("pie") for a in arches) if arches else False,
        "encrypted": any(a.get("encrypted") for a in arches),
        "has_stack_canary": all(a.get("has_stack_canary") for a in arches) if arches else False,
        "has_arc": all(a.get("has_arc") for a in arches) if arches else False,
        "has_code_signature": any(a.get("has_code_signature") for a in arches),
    }
