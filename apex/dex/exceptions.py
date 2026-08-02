"""Exception-handler analysis backed by APEX's own DEX parser.

The parsing is done by the Rust ``apex_dex_parser`` crate through the
``apex_dex_bridge`` extension. When the extension is not installed APEX says so
explicitly with an install hint rather than reporting an empty result that
looks like "this app has no exception handlers".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import apex_dex_bridge as _bridge
except Exception:  # pragma: no cover - exercised by the unavailable-path test
    _bridge = None

INSTALL_HINT = (
    "build the native DEX bridge: (cd core/dex_bridge && maturin develop --release)"
)


def bridge_available() -> bool:
    return _bridge is not None


def exception_summary_for_dex(raw: bytes) -> dict[str, Any]:
    """Return the exception-handler summary for one DEX image."""
    if _bridge is None:
        return {
            "available": False,
            "reason": "native DEX bridge is not installed",
            "hint": INSTALL_HINT,
            "methods": [],
        }
    result = dict(_bridge.exception_summary(raw))
    result["available"] = True
    return result


def scan_exceptions(extract_dir: Path) -> dict[str, Any]:
    """Aggregate exception-handler structure across every DEX in a package."""
    extract_dir = Path(extract_dir)
    dex_files = sorted(extract_dir.glob("classes*.dex"))
    if _bridge is None:
        return {
            "available": False,
            "reason": "native DEX bridge is not installed",
            "hint": INSTALL_HINT,
            "dex_files": [path.name for path in dex_files],
            "methods": [],
        }

    totals = {
        "method_count": 0,
        "methods_with_handlers": 0,
        "try_count": 0,
        "handler_count": 0,
        "exception_edges": 0,
        "unreachable_handlers": 0,
    }
    methods: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in dex_files:
        try:
            summary = exception_summary_for_dex(path.read_bytes())
        except Exception as exc:  # defensive: a malformed DEX must not abort analysis
            errors.append({"dex": path.name, "error": str(exc)})
            continue
        if not summary.get("valid", False):
            errors.append({"dex": path.name, "error": str(summary.get("error", "invalid"))})
            continue
        for key in totals:
            totals[key] += int(summary.get(key, 0))
        for method in summary.get("methods", []):
            entry = dict(method)
            entry["dex"] = path.name
            methods.append(entry)

    return {
        "available": True,
        "provider": "apex-dex-parser",
        "dex_files": [path.name for path in dex_files],
        **totals,
        "methods": methods,
        "errors": errors,
    }
