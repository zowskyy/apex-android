"""Bundled AOSP-derived permission catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "data" / "permissions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_permission(name: str) -> dict[str, Any]:
    catalog = load_catalog()
    entry = catalog.get("permissions", {}).get(name)
    if not entry:
        return {
            "name": name,
            "label": name.split(".")[-1],
            "description": None,
            "protection_level": [],
            "catalog_status": "unknown",
        }
    return {
        "name": name,
        "label": entry.get("label", name),
        "description": entry.get("description"),
        "protection_level": entry.get("protection_level", []),
        "flags": entry.get("flags", []),
        "catalog_status": "matched",
    }
