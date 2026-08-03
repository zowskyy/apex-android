"""Pure-Python MUTF-8 shim for Chaquopy (mutf8 has no Android wheel).

Vendored from mutf8 1.1.0 (MIT) — Tyler Kennedy; see VENDOR_LICENCE.txt
"""

from mutf8.mutf8 import decode_modified_utf8, encode_modified_utf8

__all__ = ["decode_modified_utf8", "encode_modified_utf8"]
