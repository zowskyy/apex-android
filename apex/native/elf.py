"""A bounded ELF symbol-table reader.

APEX parses ``.dynsym``/``.symtab`` itself rather than depending on ``readelf``,
``nm``, or a third-party ELF library. It handles 32- and 64-bit ELF in either
byte order, validates every offset before reading, and never executes or loads
the binary.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

ELF_MAGIC = b"\x7fELF"

ELFCLASS32 = 1
ELFCLASS64 = 2
ELFDATA2LSB = 1
ELFDATA2MSB = 2

SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_DYNSYM = 11

STT_FUNC = 2
STT_OBJECT = 1
STB_GLOBAL = 1
STB_WEAK = 2
SHN_UNDEF = 0

MAX_SECTIONS = 4096
MAX_SYMBOLS = 500_000


@dataclass(frozen=True)
class ElfSymbol:
    """One symbol-table entry."""

    name: str
    value: int
    size: int
    kind: str
    binding: str
    defined: bool
    table: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "size": self.size,
            "kind": self.kind,
            "binding": self.binding,
            "defined": self.defined,
            "table": self.table,
        }


def _kind_name(value: int) -> str:
    return {STT_FUNC: "func", STT_OBJECT: "object"}.get(value, f"type-{value}")


def _binding_name(value: int) -> str:
    return {STB_GLOBAL: "global", STB_WEAK: "weak", 0: "local"}.get(value, f"bind-{value}")


def _cstring(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\0", offset)
    if end == -1:
        end = len(blob)
    return blob[offset:end].decode("utf-8", "replace")


def parse_elf_symbols(data: bytes) -> dict[str, object]:
    """Parse an ELF image and return its symbols plus a small summary."""
    if len(data) < 64 or not data.startswith(ELF_MAGIC):
        return {"valid": False, "error": "not an ELF image", "symbols": []}

    ei_class = data[4]
    ei_data = data[5]
    if ei_class not in (ELFCLASS32, ELFCLASS64):
        return {"valid": False, "error": f"unsupported ELF class {ei_class}", "symbols": []}
    if ei_data not in (ELFDATA2LSB, ELFDATA2MSB):
        return {"valid": False, "error": f"unsupported ELF data order {ei_data}", "symbols": []}

    endian = "<" if ei_data == ELFDATA2LSB else ">"
    is64 = ei_class == ELFCLASS64

    try:
        if is64:
            e_shoff = struct.unpack_from(endian + "Q", data, 0x28)[0]
            e_shentsize = struct.unpack_from(endian + "H", data, 0x3A)[0]
            e_shnum = struct.unpack_from(endian + "H", data, 0x3C)[0]
        else:
            e_shoff = struct.unpack_from(endian + "I", data, 0x20)[0]
            e_shentsize = struct.unpack_from(endian + "H", data, 0x2E)[0]
            e_shnum = struct.unpack_from(endian + "H", data, 0x30)[0]
    except struct.error as exc:
        return {"valid": False, "error": f"truncated ELF header: {exc}", "symbols": []}

    if e_shoff == 0 or e_shnum == 0:
        return {
            "valid": True,
            "class": 64 if is64 else 32,
            "endian": "little" if endian == "<" else "big",
            "stripped": True,
            "symbols": [],
            "note": "no section headers; symbols unavailable",
        }

    e_shnum = min(e_shnum, MAX_SECTIONS)
    sections: list[dict[str, int]] = []
    for index in range(e_shnum):
        base = e_shoff + index * e_shentsize
        if base + e_shentsize > len(data):
            break
        try:
            if is64:
                sh_type = struct.unpack_from(endian + "I", data, base + 4)[0]
                sh_offset = struct.unpack_from(endian + "Q", data, base + 0x18)[0]
                sh_size = struct.unpack_from(endian + "Q", data, base + 0x20)[0]
                sh_link = struct.unpack_from(endian + "I", data, base + 0x28)[0]
                sh_entsize = struct.unpack_from(endian + "Q", data, base + 0x38)[0]
            else:
                sh_type = struct.unpack_from(endian + "I", data, base + 4)[0]
                sh_offset = struct.unpack_from(endian + "I", data, base + 0x10)[0]
                sh_size = struct.unpack_from(endian + "I", data, base + 0x14)[0]
                sh_link = struct.unpack_from(endian + "I", data, base + 0x18)[0]
                sh_entsize = struct.unpack_from(endian + "I", data, base + 0x24)[0]
        except struct.error:
            break
        sections.append(
            {
                "type": sh_type,
                "offset": sh_offset,
                "size": sh_size,
                "link": sh_link,
                "entsize": sh_entsize,
            }
        )

    symbols: list[ElfSymbol] = []
    sym_entry_size = 24 if is64 else 16
    for section in sections:
        if section["type"] not in (SHT_DYNSYM, SHT_SYMTAB):
            continue
        table_name = "dynsym" if section["type"] == SHT_DYNSYM else "symtab"
        str_index = section["link"]
        if str_index >= len(sections):
            continue
        str_section = sections[str_index]
        str_start = str_section["offset"]
        str_end = str_start + str_section["size"]
        if str_start >= len(data) or str_end > len(data):
            continue
        strings = data[str_start:str_end]

        entsize = section["entsize"] or sym_entry_size
        if entsize <= 0:
            continue
        count = min(section["size"] // entsize, MAX_SYMBOLS)
        for index in range(count):
            base = section["offset"] + index * entsize
            if base + sym_entry_size > len(data):
                break
            try:
                if is64:
                    st_name, st_info, _st_other, st_shndx = struct.unpack_from(
                        endian + "IBBH", data, base
                    )
                    st_value, st_size = struct.unpack_from(endian + "QQ", data, base + 8)
                else:
                    st_name, st_value, st_size = struct.unpack_from(
                        endian + "III", data, base
                    )
                    st_info, _st_other, st_shndx = struct.unpack_from(
                        endian + "BBH", data, base + 12
                    )
            except struct.error:
                break
            name = _cstring(strings, st_name)
            if not name:
                continue
            symbols.append(
                ElfSymbol(
                    name=name,
                    value=st_value,
                    size=st_size,
                    kind=_kind_name(st_info & 0xF),
                    binding=_binding_name(st_info >> 4),
                    defined=st_shndx != SHN_UNDEF,
                    table=table_name,
                )
            )

    return {
        "valid": True,
        "class": 64 if is64 else 32,
        "endian": "little" if endian == "<" else "big",
        "stripped": not symbols,
        "symbol_count": len(symbols),
        "symbols": symbols,
    }


def exported_functions(data: bytes) -> set[str]:
    """Return the names of globally visible, defined functions."""
    parsed = parse_elf_symbols(data)
    if not parsed.get("valid"):
        return set()
    return {
        symbol.name
        for symbol in parsed["symbols"]  # type: ignore[union-attr]
        if symbol.defined and symbol.kind == "func" and symbol.binding in ("global", "weak")
    }


def exported_functions_for_path(path: Path) -> set[str]:
    try:
        return exported_functions(Path(path).read_bytes())
    except OSError:
        return set()
