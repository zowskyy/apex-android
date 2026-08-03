"""Bytecode API-usage watch engine (blueprint API-1)."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.analysis import dex_metadata


@dataclass(frozen=True)
class WatchEntry:
    """Match xref callees and optional DEX string-pool hints."""

    class_pattern: str
    method_name: str
    category: str
    message: str
    severity: str = "WARN"
    string_hint: str | None = None


def collect_apk_dex_index(apk_path: Path, *, lightweight: bool = False) -> dict[str, Any]:
    """Aggregate classes, methods, edges, and strings from all DEX in an APK."""
    apk_path = Path(apk_path)
    index: dict[str, Any] = {
        "classes": [],
        "methods": [],
        "edges": [],
        "strings": [],
        "errors": [],
        "lightweight": lightweight,
    }
    with zipfile.ZipFile(apk_path) as archive:
        dex_names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name.replace("\\", "/"))
        )
        for dex_name in dex_names:
            try:
                meta = dex_metadata(
                    archive.read(dex_name),
                    dex_name,
                    lightweight=lightweight,
                )
                for key in ("classes", "methods", "edges", "strings"):
                    index[key].extend(meta.get(key) or [])
                for err in meta.get("errors") or []:
                    index["errors"].append(err)
            except Exception as exc:
                index["errors"].append({"dex": dex_name, "error": str(exc)})
    return index


def _callee_matches(callee: str, entry: WatchEntry) -> bool:
    if f"::{entry.method_name}" not in callee:
        return False
    return entry.class_pattern.replace(".", "/") in callee.replace(".", "/")


def _string_hint_matches(hint: str | None, blob: str) -> bool:
    if not hint:
        return True
    return bool(re.search(hint, blob))


def scan_watchlist(
    dex_index: dict[str, Any],
    watchlist: list[WatchEntry],
) -> list[dict[str, Any]]:
    """Query xref edges and optional string hints against a watchlist."""
    findings: list[dict[str, Any]] = []
    strings_blob = "\n".join(str(s) for s in dex_index.get("strings") or [])
    seen: set[str] = set()

    for edge in dex_index.get("edges") or []:
        callee = str(edge.get("callee", ""))
        caller = f"{edge.get('caller_class')}::{edge.get('caller_method')}"
        for entry in watchlist:
            if not _callee_matches(callee, entry):
                continue
            if not _string_hint_matches(entry.string_hint, strings_blob):
                continue
            key = f"{entry.category}:{callee}"
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "severity": entry.severity.lower(),
                    "category": entry.category,
                    "message": entry.message,
                    "evidence": f"{caller} -> {callee}",
                }
            )

    if not dex_index.get("edges"):
        for entry in watchlist:
            if entry.string_hint and re.search(entry.string_hint, strings_blob):
                key = f"string:{entry.category}"
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "severity": entry.severity.lower(),
                        "category": entry.category,
                        "message": entry.message + " (string-pool hint only — no xref on this tier)",
                        "evidence": entry.string_hint,
                    }
                )
    return findings


def scan_apk_api_watch(
    apk_path: Path,
    watchlist: list[WatchEntry],
    *,
    lightweight: bool | None = None,
) -> list[dict[str, Any]]:
    if lightweight is None:
        try:
            from apex.device_profile import limits

            profile = limits()
            lightweight = bool(profile.get("dex_lightweight")) or profile.get("engine_mode") == "on_device"
        except Exception:
            lightweight = False
    index = collect_apk_dex_index(apk_path, lightweight=lightweight)
    return scan_watchlist(index, watchlist)
