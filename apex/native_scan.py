"""Native library (.so) ELF inspection without external readelf."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from typing import Any

PT_GNU_STACK = 0x6474e551
PF_X = 0x1
ELFMAG = b"\x7fELF"
PAGE_16K = 16384


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def inspect_elf(data: bytes) -> dict[str, Any]:
    """Parse ELF header/program headers for hardening signals."""
    result: dict[str, Any] = {
        "format": "unknown",
        "pie": False,
        "executable_stack": False,
        "relro": False,
        "segment_align_16k": True,
        "findings": [],
    }
    if len(data) < 52 or data[:4] != ELFMAG:
        return result

    ei_class = data[4]
    if ei_class == 1:  # ELF32
        result["format"] = "ELF32"
        e_type = _u16(data, 16)
        e_phoff = _u32(data, 28)
        e_phentsize = _u16(data, 42)
        e_phnum = _u16(data, 44)
        ph_parse = _parse_ph32
    elif ei_class == 2:  # ELF64
        result["format"] = "ELF64"
        e_type = _u16(data, 16)
        e_phoff = _u64(data, 32)
        e_phentsize = _u16(data, 54)
        e_phnum = _u16(data, 56)
        ph_parse = _parse_ph64
    else:
        return result

    result["pie"] = e_type == 3  # ET_DYN

    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        if offset + e_phentsize > len(data):
            break
        ph = ph_parse(data, offset)
        p_type = ph["type"]
        p_flags = ph["flags"]
        p_align = ph["align"]
        if p_type == PT_GNU_STACK and (p_flags & PF_X):
            result["executable_stack"] = True
            result["findings"].append(
                {
                    "severity": "high",
                    "category": "native-exec-stack",
                    "message": "GNU_STACK segment allows executable stack",
                }
            )
        if p_type == 1 and p_align > 0 and p_align < PAGE_16K:  # PT_LOAD
            result["segment_align_16k"] = False
        if p_type == 0x6474e552:  # PT_GNU_RELRO
            result["relro"] = True

    if not result["pie"] and e_type == 2:  # ET_EXEC
        result["findings"].append(
            {
                "severity": "medium",
                "category": "native-no-pie",
                "message": "ELF built as position-dependent executable (no PIE)",
            }
        )
    if not result["segment_align_16k"]:
        result["findings"].append(
            {
                "severity": "medium",
                "category": "native-16k-align",
                "message": "LOAD segment alignment below 16 KB (future Android page-size requirement)",
            }
        )
    return result


def _parse_ph32(data: bytes, offset: int) -> dict[str, int]:
    return {
        "type": _u32(data, offset),
        "flags": _u32(data, offset + 24),
        "align": _u32(data, offset + 28),
    }


def _parse_ph64(data: bytes, offset: int) -> dict[str, int]:
    return {
        "type": _u32(data, offset),
        "flags": _u32(data, offset + 4),
        "align": _u64(data, offset + 48),
    }


def scan_apk_native_libs(apk_path: Path, max_libs: int = 64) -> list[dict[str, Any]]:
    """Scan lib/**/*.so entries inside an APK."""
    apk_path = Path(apk_path)
    findings: list[dict[str, Any]] = []
    inspected = 0
    with zipfile.ZipFile(apk_path) as archive:
        for name in sorted(archive.namelist()):
            normalized = name.replace("\\", "/")
            if "/lib/" not in normalized or not normalized.endswith(".so"):
                continue
            if inspected >= max_libs:
                break
            inspected += 1
            try:
                raw = archive.read(name)
            except Exception:
                continue
            report = inspect_elf(raw)
            for item in report.get("findings") or []:
                findings.append(
                    {
                        "severity": item.get("severity", "medium"),
                        "category": item.get("category", "native"),
                        "evidence": name,
                        "message": str(item.get("message", "")),
                    }
                )
    return findings
