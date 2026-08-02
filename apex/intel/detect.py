"""Detect trackers and third-party libraries from extracted identifiers.

Detection is evidence-based: every match records the exact identifiers that
triggered it. Nothing here is presented as a malware verdict; a tracker match
means the SDK's namespace is present in the app, which is a privacy signal.
"""

from __future__ import annotations

from typing import Any, Iterable

from apex.intel.signatures import android_index, ios_index


def _android_prefixes(identifier: str) -> list[str]:
    """Cumulative dotted prefixes of a class/package name.

    ``com.google.android.gms.ads.Foo`` -> ``com``, ``com.google``, ...
    """
    parts = identifier.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def detect_android(class_names: Iterable[str]) -> list[dict[str, Any]]:
    """Match dotted Android class/package names against the signature set."""
    index = android_index()
    prefix_to_targets: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for prefix, kind, entry in index:
        prefix_to_targets.setdefault(prefix, []).append((kind, entry))

    matched: dict[str, dict[str, Any]] = {}
    for name in class_names:
        if not name:
            continue
        for prefix in _android_prefixes(name):
            targets = prefix_to_targets.get(prefix)
            if not targets:
                continue
            for kind, entry in targets:
                record = matched.setdefault(
                    entry["id"],
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "kind": kind,
                        "categories": entry.get("categories", []),
                        "website": entry.get("website"),
                        "platform": "android",
                        "matched_prefixes": set(),
                    },
                )
                record["matched_prefixes"].add(prefix)
    return _finalize(matched)


def detect_ios(tokens: Iterable[str]) -> list[dict[str, Any]]:
    """Match iOS framework/library tokens against the signature set."""
    index = ios_index()
    matched: dict[str, dict[str, Any]] = {}
    for token in tokens:
        if not token:
            continue
        base = token.split(".")[0].lower()
        for kind, entry in index.get(base, []):
            record = matched.setdefault(
                entry["id"],
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "kind": kind,
                    "categories": entry.get("categories", []),
                    "website": entry.get("website"),
                    "platform": "ios",
                    "matched_prefixes": set(),
                },
            )
            record["matched_prefixes"].add(token)
    return _finalize(matched)


def _finalize(matched: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for record in matched.values():
        record["evidence"] = sorted(record.pop("matched_prefixes"))
        results.append(record)
    results.sort(key=lambda item: (item["kind"] != "tracker", item["name"].lower()))
    return results


def detect_components(
    *, android_classes: Iterable[str] | None = None, ios_tokens: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """Unified entry point returning both tracker and library detections."""
    results: list[dict[str, Any]] = []
    if android_classes is not None:
        results.extend(detect_android(android_classes))
    if ios_tokens is not None:
        results.extend(detect_ios(ios_tokens))
    return results


def summarize_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up detections into counts by kind and category."""
    trackers = [d for d in detections if d["kind"] == "tracker"]
    libraries = [d for d in detections if d["kind"] == "library"]
    categories: dict[str, int] = {}
    for det in trackers:
        for category in det.get("categories", []):
            categories[category] = categories.get(category, 0) + 1
    return {
        "tracker_count": len(trackers),
        "library_count": len(libraries),
        "trackers": trackers,
        "libraries": libraries,
        "tracker_categories": dict(sorted(categories.items())),
    }
