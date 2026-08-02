#!/usr/bin/env python3
"""Build a minimal but structurally valid DEX containing real try/catch tables.

The Android SDK is not available in APEX's test environment, so this script
assembles the DEX container itself: header, string/type/method id tables, a
class_def, a class_data_item, and a code_item whose instruction stream is
followed by a genuine ``try_item`` array and ``encoded_catch_handler_list``.

The resulting file exercises the AND-03 path end to end (Rust parser through
the PyO3 bridge) with real bytes rather than a synthetic in-memory structure.

Usage:
    python scripts/generate_exception_dex.py [--clean]
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

HEADER_SIZE = 0x70
ENDIAN_CONSTANT = 0x12345678

# Class, superclass, catch type, method name, shorty.
STRINGS = [
    "Lcom/apex/Guarded;",
    "Ljava/lang/Object;",
    "Ljava/lang/Exception;",
    "Ljava/lang/IllegalStateException;",
    "risky",
    "V",
]
# type_idx -> string index
TYPE_TO_STRING = [0, 1, 2, 3]

CLASS_TYPE_IDX = 0
SUPER_TYPE_IDX = 1
EXCEPTION_TYPE_IDX = 2
ISE_TYPE_IDX = 3
METHOD_NAME_STRING_IDX = 4


def uleb128(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def sleb128_byte(value: int) -> bytes:
    """Single-byte SLEB128 for the small magnitudes this fixture uses."""
    assert -64 <= value < 64, "fixture only needs single-byte SLEB128"
    return bytes([value & 0x7F])


def mutf8_string(text: str) -> bytes:
    """string_data_item: ULEB128 utf16 length, then MUTF-8 bytes, then NUL."""
    return uleb128(len(text)) + text.encode("utf-8") + b"\x00"


def build_code_item() -> bytes:
    """A method with one protected range, two typed handlers and a catch-all.

    Instruction stream (6 code units):
        0: nop                (protected)
        1: nop                (protected)
        2: goto +4  -> 6      (protected, leaves the range)
        3: return-void        typed handler for Exception
        4: return-void        typed handler for IllegalStateException
        5: return-void        catch-all handler
        6: return-void        normal exit
    """
    insns = [
        0x0000,  # nop
        0x0000,  # nop
        (4 << 8) | 0x28,  # goto +4
        0x000E,  # return-void  (handler A @3)
        0x000E,  # return-void  (handler B @4)
        0x000E,  # return-void  (catch-all @5)
        0x000E,  # return-void  (exit @6)
    ]
    insns_size = len(insns)

    # Handler list first so try_item.handler_off can reference real offsets.
    handler_list = bytearray()
    handler_list += uleb128(1)  # one encoded_catch_handler
    first_handler_off = len(handler_list)
    handler_list += sleb128_byte(-2)  # two typed handlers plus a catch-all
    handler_list += uleb128(EXCEPTION_TYPE_IDX) + uleb128(3)
    handler_list += uleb128(ISE_TYPE_IDX) + uleb128(4)
    handler_list += uleb128(5)  # catch_all_addr

    tries = struct.pack("<IHH", 0, 3, first_handler_off)  # start=0, count=3

    body = bytearray()
    body += struct.pack("<HHHH", 2, 0, 0, 1)  # registers, ins, outs, tries_size
    body += struct.pack("<II", 0, insns_size)  # debug_info_off, insns_size
    for unit in insns:
        body += struct.pack("<H", unit)
    if insns_size % 2 == 1:
        body += b"\x00\x00"  # alignment padding before the try table
    body += tries
    body += handler_list
    return bytes(body)


def build_dex() -> bytes:
    string_count = len(STRINGS)
    type_count = len(TYPE_TO_STRING)
    method_count = 1
    class_count = 1

    string_ids_off = HEADER_SIZE
    type_ids_off = string_ids_off + string_count * 4
    method_ids_off = type_ids_off + type_count * 4
    class_defs_off = method_ids_off + method_count * 8
    data_off = class_defs_off + class_count * 32

    # Data section: string_data items, then code_item, then class_data.
    data = bytearray()
    string_data_offsets: list[int] = []
    for text in STRINGS:
        string_data_offsets.append(data_off + len(data))
        data += mutf8_string(text)

    while (data_off + len(data)) % 4:
        data += b"\x00"
    code_off = data_off + len(data)
    data += build_code_item()

    class_data_off = data_off + len(data)
    class_data = bytearray()
    class_data += uleb128(0)  # static_fields_size
    class_data += uleb128(0)  # instance_fields_size
    class_data += uleb128(1)  # direct_methods_size
    class_data += uleb128(0)  # virtual_methods_size
    class_data += uleb128(0)  # method_idx_diff (first method -> idx 0)
    class_data += uleb128(0x0009)  # access_flags: public static
    class_data += uleb128(code_off)
    data += class_data

    out = bytearray()
    out += b"dex\n035\x00"
    out += struct.pack("<I", 0)  # checksum (not verified by APEX's parser)
    out += b"\x00" * 20  # signature
    file_size_pos = len(out)
    out += struct.pack("<I", 0)  # file_size, patched below
    out += struct.pack("<I", HEADER_SIZE)
    out += struct.pack("<I", ENDIAN_CONSTANT)
    out += struct.pack("<II", 0, 0)  # link_size, link_off
    out += struct.pack("<I", 0)  # map_off
    out += struct.pack("<II", string_count, string_ids_off)
    out += struct.pack("<II", type_count, type_ids_off)
    out += struct.pack("<II", 0, 0)  # proto_ids
    out += struct.pack("<II", 0, 0)  # field_ids
    out += struct.pack("<II", method_count, method_ids_off)
    out += struct.pack("<II", class_count, class_defs_off)
    out += struct.pack("<II", len(data), data_off)
    assert len(out) == HEADER_SIZE, f"header is {len(out)} bytes, expected {HEADER_SIZE}"

    for offset in string_data_offsets:
        out += struct.pack("<I", offset)
    for string_index in TYPE_TO_STRING:
        out += struct.pack("<I", string_index)
    # method_id_item: class_idx u16, proto_idx u16, name_idx u32
    out += struct.pack("<HHI", CLASS_TYPE_IDX, 0, METHOD_NAME_STRING_IDX)
    # class_def_item: 8 u32 fields
    out += struct.pack(
        "<IIIIIIII",
        CLASS_TYPE_IDX,
        0x0001,  # public
        SUPER_TYPE_IDX,
        0,  # interfaces_off
        0xFFFFFFFF,  # source_file_idx NO_INDEX
        0,  # annotations_off
        class_data_off,
        0,  # static_values_off
    )
    assert len(out) == data_off, f"data starts at {len(out)}, expected {data_off}"
    out += data

    struct.pack_into("<I", out, file_size_pos, len(out))
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="rebuild even if present")
    args = parser.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)
    dex_path = FIXTURES / "exception_test.dex"
    apk_path = FIXTURES / "exception_test.apk"
    if dex_path.is_file() and apk_path.is_file() and not args.clean:
        print(f"fixture already present: {dex_path}")
        return 0

    blob = build_dex()
    dex_path.write_bytes(blob)
    with zipfile.ZipFile(apk_path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"<manifest/>")
        archive.writestr("classes.dex", blob)
    print(f"Wrote {dex_path} ({len(blob)} bytes) and {apk_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
