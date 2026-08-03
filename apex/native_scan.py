"""Native library (.so) ELF inspection without external readelf."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from typing import Any

PT_LOAD = 1
PT_DYNAMIC = 2
PT_GNU_STACK = 0x6474e551
PT_GNU_RELRO = 0x6474e552
PF_X = 0x1
ELFMAG = b"\x7fELF"
PAGE_16K = 16384
DT_BIND_NOW = 24
DT_FLAGS = 30
DF_BIND_NOW = 0x8

# Dynamic symbol names that warrant manual review when imported.
_DANGEROUS_SYMBOLS = frozenset(
    {
        "system",
        "popen",
        "strcpy",
        "strcat",
        "sprintf",
        "gets",
        "scanf",
        "vsprintf",
        "dlopen",
    }
)


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _parse_dynamic_bind_now(data: bytes, ph_offset: int, ph_entsize: int, ph_num: int) -> bool:
    """Return True when BIND_NOW / DF_BIND_NOW is present in PT_DYNAMIC."""
    for index in range(ph_num):
        offset = ph_offset + index * ph_entsize
        if offset + ph_entsize > len(data):
            break
        p_type = _u32(data, offset)
        if p_type != PT_DYNAMIC:
            continue
        if ph_entsize >= 56:  # ELF64 phdr
            p_offset = _u64(data, offset + 8)
            p_filesz = _u64(data, offset + 32)
        else:  # ELF32 phdr
            p_offset = _u32(data, offset + 4)
            p_filesz = _u32(data, offset + 16)
        end = min(len(data), p_offset + p_filesz)
        pos = p_offset
        while pos + 16 <= end:
            d_tag = _u64(data, pos) if ph_entsize >= 56 else _u32(data, pos)
            d_val = _u64(data, pos + 8) if ph_entsize >= 56 else _u32(data, pos + 4)
            if d_tag == 0:
                break
            if d_tag == DT_BIND_NOW or (d_tag == DT_FLAGS and d_val & DF_BIND_NOW):
                return True
            pos += 16 if ph_entsize >= 56 else 8
    return False


def _dangerous_symbols_present(data: bytes) -> list[str]:
    """Best-effort dynstr scan for risky imported symbol names."""
    hits: list[str] = []
    for name in _DANGEROUS_SYMBOLS:
        if f"{name}\x00".encode() in data or name.encode() in data:
            hits.append(name)
    return hits


def inspect_elf(data: bytes, *, min_sdk: int | None = None) -> dict[str, Any]:
    """Parse ELF header/program headers for hardening signals."""
    result: dict[str, Any] = {
        "format": "unknown",
        "pie": False,
        "executable_stack": False,
        "relro": False,
        "relro_full": False,
        "stack_protector": False,
        "segment_align_16k": True,
        "dangerous_symbols": [],
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
        ph_entsize = e_phentsize
    elif ei_class == 2:  # ELF64
        result["format"] = "ELF64"
        e_type = _u16(data, 16)
        e_phoff = _u64(data, 32)
        e_phentsize = _u16(data, 54)
        e_phnum = _u16(data, 56)
        ph_parse = _parse_ph64
        ph_entsize = e_phentsize
    else:
        return result

    result["pie"] = e_type == 3  # ET_DYN
    result["stack_protector"] = b"__stack_chk_fail" in data
    result["dangerous_symbols"] = _dangerous_symbols_present(data)
    bind_now = _parse_dynamic_bind_now(data, e_phoff, ph_entsize, e_phnum)
    saw_load = False

    for index in range(e_phnum):
        offset = e_phoff + index * ph_entsize
        if offset + ph_entsize > len(data):
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
                    "confidence": "HIGH",
                    "remediation": "Rebuild with -Wl,-z,noexecstack and verify linker flags",
                }
            )
        if p_type == PT_LOAD:
            saw_load = True
            if p_align > 0 and p_align < PAGE_16K:
                result["segment_align_16k"] = False
        if p_type == PT_GNU_RELRO:
            result["relro"] = True
            result["relro_full"] = bind_now

    if not saw_load:
        result["segment_align_16k"] = False

    if not result["pie"] and e_type == 2:  # ET_EXEC
        result["findings"].append(
            {
                "severity": "medium",
                "category": "native-no-pie",
                "message": "ELF built as position-dependent executable (no PIE)",
                "confidence": "HIGH",
                "remediation": "Rebuild with -fPIC and link as shared object / PIE executable",
            }
        )

    align_severity = "medium"
    if min_sdk is not None and min_sdk >= 35:
        align_severity = "high"
    if not result["segment_align_16k"]:
        result["findings"].append(
            {
                "severity": align_severity,
                "category": "native-16k-align",
                "message": (
                    "LOAD segment alignment below 16 KB "
                    "(Google Play requirement for apps targeting API 35+ with native code)"
                ),
                "confidence": "HIGH" if min_sdk and min_sdk >= 35 else "MEDIUM",
                "remediation": "Rebuild native libs with -Wl,-z,max-page-size=16384",
            }
        )

    if not result["relro"]:
        result["findings"].append(
            {
                "severity": "medium",
                "category": "native-no-relro",
                "message": "No PT_GNU_RELRO segment — RELRO hardening missing",
                "confidence": "HIGH",
                "remediation": "Link with -Wl,-z,relro",
            }
        )
    elif not result["relro_full"]:
        result["findings"].append(
            {
                "severity": "low",
                "category": "native-partial-relro",
                "message": "Partial RELRO (BIND_NOW not observed) — prefer full RELRO",
                "confidence": "MEDIUM",
                "remediation": "Link with -Wl,-z,relro,-z,now for full RELRO",
            }
        )

    if not result["stack_protector"]:
        result["findings"].append(
            {
                "severity": "low",
                "category": "native-no-stack-protector",
                "message": "__stack_chk_fail symbol not found — stack protector may be absent",
                "confidence": "LOW",
                "remediation": "Rebuild with -fstack-protector-strong",
            }
        )

    for sym in result["dangerous_symbols"]:
        result["findings"].append(
            {
                "severity": "medium",
                "category": "native-dangerous-symbol",
                "message": f"Dangerous dynamic symbol reference: {sym}",
                "confidence": "MEDIUM",
                "remediation": f"Review use of {sym}(); prefer safer APIs",
                "evidence": sym,
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


def scan_apk_native_libs(
    apk_path: Path,
    max_libs: int = 64,
    *,
    min_sdk: int | None = None,
) -> list[dict[str, Any]]:
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
            report = inspect_elf(raw, min_sdk=min_sdk)
            for item in report.get("findings") or []:
                findings.append(
                    {
                        "severity": item.get("severity", "medium"),
                        "category": item.get("category", "native"),
                        "evidence": item.get("evidence", name),
                        "message": str(item.get("message", "")),
                        "confidence": item.get("confidence", "HIGH"),
                        "remediation": item.get("remediation", ""),
                    }
                )
    return findings
