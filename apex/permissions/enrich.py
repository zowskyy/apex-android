"""Merge declared and granted permission state."""

from __future__ import annotations

import re
from typing import Any

from .catalog import lookup_permission


def enrich_declared(permissions: list[str]) -> list[dict[str, Any]]:
    return [
        {
            **lookup_permission(name),
            "declared": True,
            "granted": None,
            "grant_source": None,
        }
        for name in permissions
    ]


def parse_granted_from_dumpsys(dumpsys: str) -> dict[str, bool]:
    granted: dict[str, bool] = {}
    current: str | None = None
    for line in dumpsys.splitlines():
        if line.strip().startswith("android.permission."):
            current = line.strip().split()[0]
        if current and "granted=" in line:
            granted[current] = "granted=true" in line.lower()
            current = None
        match = re.search(r"(android\.permission\.[A-Z0-9_.]+): granted=(true|false)", line)
        if match:
            granted[match.group(1)] = match.group(2) == "true"
    return granted


def enrich_with_grants(
    declared: list[str],
    dumpsys: str | None,
) -> list[dict[str, Any]]:
    granted_map = parse_granted_from_dumpsys(dumpsys or "")
    enriched = enrich_declared(declared)
    for item in enriched:
        name = item["name"]
        if name in granted_map:
            item["granted"] = granted_map[name]
            item["grant_source"] = "adb.dumpsys"
        else:
            item["granted"] = None
            item["grant_source"] = None
    return enriched
