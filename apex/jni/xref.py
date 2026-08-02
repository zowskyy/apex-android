"""Unified Dalvik + native cross-reference graph.

Correlates ``native``-declared Java methods with exported symbols in the
bundled ELF libraries so a JNI boundary crossing becomes a real edge instead of
a manual lookup. Resolution is bidirectional and every unresolved method states
why, rather than being dropped or guessed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.jni.mangle import candidate_symbols, jni_long_name, jni_short_name
from apex.native.elf import parse_elf_symbols

_LOAD_LIBRARY_CALLEES = (
    "java.lang.System::loadLibrary",
    "java.lang.System::load",
    "java.lang.Runtime::loadLibrary",
    "java.lang.Runtime::load",
)


def detect_load_library(dex_index: dict[str, Any]) -> dict[str, Any]:
    """Find evidence that the app loads a native library."""
    call_sites: list[dict[str, str]] = []
    for edge in dex_index.get("edges", []):
        callee = str(edge.get("callee", ""))
        if any(callee.startswith(prefix) for prefix in _LOAD_LIBRARY_CALLEES):
            call_sites.append(
                {
                    "caller_class": str(edge.get("caller_class", "")),
                    "caller_method": str(edge.get("caller_method", "")),
                    "callee": callee,
                }
            )
    return {"call_sites": call_sites, "count": len(call_sites)}


def native_methods(dex_index: dict[str, Any]) -> list[dict[str, str]]:
    """Java methods declared with the ``native`` modifier."""
    results: list[dict[str, str]] = []
    for method in dex_index.get("methods", []):
        access = str(method.get("access", ""))
        if "native" not in access.split():
            continue
        results.append(
            {
                "class": str(method.get("class", "")),
                "name": str(method.get("name", "")),
                "descriptor": str(method.get("descriptor", "")),
                "dex": str(method.get("dex", "")),
            }
        )
    return results


def library_symbol_index(
    extract_dir: Path, native_index: dict[str, Any]
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    """Map each bundled library to its exported function names."""
    index: dict[str, set[str]] = {}
    summaries: list[dict[str, Any]] = []
    for library in native_index.get("native_libs", []):
        relative = str(library.get("path", ""))
        path = Path(extract_dir) / relative
        try:
            data = path.read_bytes()
        except OSError as exc:
            summaries.append({"path": relative, "error": str(exc), "symbol_count": 0})
            continue
        parsed = parse_elf_symbols(data)
        if not parsed.get("valid"):
            summaries.append(
                {
                    "path": relative,
                    "error": str(parsed.get("error", "unparsable")),
                    "symbol_count": 0,
                }
            )
            continue
        exports = {
            symbol.name
            for symbol in parsed["symbols"]  # type: ignore[union-attr]
            if symbol.defined
            and symbol.kind == "func"
            and symbol.binding in ("global", "weak")
        }
        index[relative] = exports
        summaries.append(
            {
                "path": relative,
                "abi": library.get("abi", ""),
                "class": parsed.get("class"),
                "endian": parsed.get("endian"),
                "symbol_count": len(exports),
                "stripped": bool(parsed.get("stripped")),
                "registers_natives": "JNI_OnLoad" in exports or "RegisterNatives" in exports,
            }
        )
    return index, summaries


def build_jni_graph(
    dex_index: dict[str, Any],
    native_index: dict[str, Any],
    extract_dir: Path,
) -> dict[str, Any]:
    """Resolve native methods to library exports and emit JNI edges."""
    symbol_index, libraries = library_symbol_index(Path(extract_dir), native_index)
    declared = native_methods(dex_index)
    loader = detect_load_library(dex_index)

    edges: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    any_dynamic_registration = any(lib.get("registers_natives") for lib in libraries)

    for method in declared:
        expected = candidate_symbols(method["class"], method["name"], method["descriptor"])
        match: tuple[str, str] | None = None
        for library, exports in symbol_index.items():
            for symbol in expected:
                if symbol in exports:
                    match = (library, symbol)
                    break
            if match:
                break
        java_ref = f"{method['class']}::{method['name']}{method['descriptor']}"
        if match:
            library, symbol = match
            edges.append(
                {
                    "kind": "jni",
                    "java": java_ref,
                    "java_class": method["class"],
                    "java_method": method["name"],
                    "descriptor": method["descriptor"],
                    "library": library,
                    "symbol": symbol,
                    "binding": "static",
                    "resolved": True,
                }
            )
        else:
            unresolved.append(
                {
                    "java": java_ref,
                    "expected_symbols": expected,
                    "resolved": False,
                    "reason": (
                        "no matching export; likely registered dynamically via "
                        "RegisterNatives"
                        if any_dynamic_registration
                        else "no matching export in any bundled library"
                    ),
                }
            )

    return {
        "edges": edges,
        "unresolved": unresolved,
        "libraries": libraries,
        "native_method_count": len(declared),
        "resolved_count": len(edges),
        "unresolved_count": len(unresolved),
        "load_library": loader,
        "dynamic_registration_suspected": any_dynamic_registration,
    }


def resolve_symbol_to_java(graph: dict[str, Any], symbol: str) -> list[str]:
    """Reverse lookup: native symbol -> declaring Java method(s)."""
    return [edge["java"] for edge in graph.get("edges", []) if edge.get("symbol") == symbol]


def resolve_java_to_symbol(graph: dict[str, Any], java_ref: str) -> list[str]:
    """Forward lookup: Java method -> native symbol(s)."""
    return [edge["symbol"] for edge in graph.get("edges", []) if edge.get("java") == java_ref]


__all__ = [
    "build_jni_graph",
    "detect_load_library",
    "native_methods",
    "library_symbol_index",
    "resolve_symbol_to_java",
    "resolve_java_to_symbol",
    "jni_short_name",
    "jni_long_name",
]
