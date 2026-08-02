"""Unified multidex symbol table and cross-reference resolution.

Android splits large apps across ``classes.dex``, ``classes2.dex``, and so on.
Per-DEX analysis cannot see a callee that lives in a different DEX file, so a
call across that boundary is left dangling.

APEX resolves those edges itself: it builds one symbol table spanning every
DEX in the package, then resolves each call edge against that table and
records which DEX defines each endpoint. The resolution logic is APEX's own
and does not depend on any particular DEX parser's cross-reference engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Guard against pathological inputs while staying far above any real app.
MAX_SYMBOLS = 4_000_000


@dataclass(frozen=True)
class MethodSymbol:
    """A method definition located in a specific DEX file."""

    key: str
    class_name: str
    method_name: str
    descriptor: str
    dex: str

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "class": self.class_name,
            "method": self.method_name,
            "descriptor": self.descriptor,
            "dex": self.dex,
        }


def method_key(class_name: str, method_name: str, descriptor: str) -> str:
    """Canonical symbol key shared by definitions and call edges."""
    return f"{class_name}::{method_name}{descriptor}"


def build_symbol_table(dex_index: dict[str, Any]) -> dict[str, MethodSymbol]:
    """Build one symbol table spanning every DEX in a merged index."""
    table: dict[str, MethodSymbol] = {}
    for method in dex_index.get("methods", []):
        class_name = str(method.get("class", ""))
        name = str(method.get("name", ""))
        if not class_name or not name:
            continue
        descriptor = str(method.get("descriptor", ""))
        key = method_key(class_name, name, descriptor)
        if key in table:
            continue
        table[key] = MethodSymbol(
            key=key,
            class_name=class_name,
            method_name=name,
            descriptor=descriptor,
            dex=str(method.get("dex", "")),
        )
        if len(table) > MAX_SYMBOLS:
            break
    return table


def _class_dex_map(dex_index: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for cls in dex_index.get("classes", []):
        name = str(cls.get("name", ""))
        if name and name not in mapping:
            mapping[name] = str(cls.get("dex", ""))
    return mapping


def duplicate_classes(dex_index: dict[str, Any]) -> list[dict[str, Any]]:
    """Classes defined in more than one DEX file, which is ambiguous."""
    seen: dict[str, list[str]] = {}
    for cls in dex_index.get("classes", []):
        name = str(cls.get("name", ""))
        dex = str(cls.get("dex", ""))
        if not name:
            continue
        seen.setdefault(name, [])
        if dex not in seen[name]:
            seen[name].append(dex)
    return [
        {"class": name, "dex_files": sorted(dex_files)}
        for name, dex_files in sorted(seen.items())
        if len(dex_files) > 1
    ]


def resolve_cross_dex(dex_index: dict[str, Any]) -> dict[str, Any]:
    """Resolve every call edge against the unified symbol table.

    Returns the resolved edge list plus statistics. Each edge gains
    ``resolved``, ``caller_dex`` and ``callee_dex``. Edges whose callee is not
    defined in the package (framework or runtime methods) are reported as
    unresolved with a reason rather than silently dropped or invented.
    """
    table = build_symbol_table(dex_index)
    class_dex = _class_dex_map(dex_index)

    resolved_edges: list[dict[str, Any]] = []
    cross_dex = 0
    unresolved = 0
    for edge in dex_index.get("edges", []):
        callee = str(edge.get("callee", ""))
        caller_class = str(edge.get("caller_class", ""))
        symbol = table.get(callee)
        caller_dex = class_dex.get(caller_class, "")
        callee_dex = symbol.dex if symbol else ""
        is_cross = bool(symbol) and bool(caller_dex) and caller_dex != callee_dex
        if symbol is None:
            unresolved += 1
        if is_cross:
            cross_dex += 1
        entry = dict(edge)
        entry.update(
            {
                "caller_dex": caller_dex,
                "callee_dex": callee_dex,
                "resolved": symbol is not None,
                "cross_dex": is_cross,
            }
        )
        if symbol is None:
            entry["unresolved_reason"] = "callee is not defined in this package"
        resolved_edges.append(entry)

    return {
        "edges": resolved_edges,
        "symbol_count": len(table),
        "dex_files": sorted({symbol.dex for symbol in table.values() if symbol.dex}),
        "edge_count": len(resolved_edges),
        "cross_dex_edges": cross_dex,
        "unresolved_edges": unresolved,
        "duplicate_classes": duplicate_classes(dex_index),
    }


def lookup(table: dict[str, MethodSymbol], callee: str) -> MethodSymbol | None:
    """Resolve a call target string against the unified symbol table."""
    return table.get(callee)
