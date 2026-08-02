"""Load and index the bundled tracker/library signature set.

The signature file is offline, version-controlled data with recorded provenance.
No network access is required or performed to detect trackers and libraries.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "trackers.json"


@functools.lru_cache(maxsize=1)
def load_signatures() -> dict[str, Any]:
    """Return the parsed signature document (cached)."""
    with _DATA_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def signature_stats() -> dict[str, Any]:
    """Return a small summary suitable for `doctor` and the web UI."""
    data = load_signatures()
    return {
        "schema_version": data.get("schema_version"),
        "tracker_count": len(data.get("trackers", [])),
        "library_count": len(data.get("libraries", [])),
        "categories": data.get("provenance", {}).get("categories", []),
        "source": "bundled offline signature set",
        "path": str(_DATA_PATH),
    }


@functools.lru_cache(maxsize=1)
def _android_index() -> list[tuple[str, str, dict[str, Any]]]:
    """List of (prefix, kind, entry) for Android dotted-package matching."""
    data = load_signatures()
    index: list[tuple[str, str, dict[str, Any]]] = []
    for kind, singular in (("trackers", "tracker"), ("libraries", "library")):
        for entry in data.get(kind, []):
            for prefix in entry.get("android", []):
                index.append((prefix, singular, entry))
    return index


@functools.lru_cache(maxsize=1)
def _ios_index() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Map of lowercase framework/token -> [(kind, entry)] for iOS matching."""
    data = load_signatures()
    index: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for kind, singular in (("trackers", "tracker"), ("libraries", "library")):
        for entry in data.get(kind, []):
            for token in entry.get("ios", []):
                index.setdefault(token.lower(), []).append((singular, entry))
    return index


def android_index() -> list[tuple[str, str, dict[str, Any]]]:
    return _android_index()


def ios_index() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    return _ios_index()
