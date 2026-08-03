#!/usr/bin/env python3
"""Optional OSV API refresh for curated libraries in apex/data/cve_db.json.

Merges advisory metadata into ~/.apex/cve_db.json (or --out path).
Network required. Falls back to bundled DB on failure.

Usage:
  python scripts/release/fetch_cve_osv.py
  python scripts/release/fetch_cve_osv.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE = _ROOT / "apex" / "data" / "cve_db.json"
_USER = Path.home() / ".apex" / "cve_db.json"
_OSV_URL = "https://api.osv.dev/v1/query"

# Curated OSV package coordinates for bundled libraries
_OSV_PACKAGES: list[dict[str, str]] = [
    {"package": {"name": "okhttp", "ecosystem": "Maven"}, "library_key": "okhttp3"},
    {"package": {"name": "gson", "ecosystem": "Maven"}, "library_key": "com.google.gson"},
]


def _osv_query(package: dict[str, str]) -> list[dict[str, Any]]:
    payload = json.dumps({"package": package}).encode("utf-8")
    req = urllib.request.Request(
        _OSV_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("vulns") or []


def merge_osv_into_db(db: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    libraries = {str(lib.get("package_prefix")): lib for lib in db.get("libraries") or []}
    for entry in _OSV_PACKAGES:
        key = entry["library_key"]
        lib = libraries.get(key)
        if not lib:
            continue
        try:
            vulns = _osv_query(entry["package"])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"OSV skip {key}: {exc}", file=sys.stderr)
            continue
        seen: set[str] = set()
        for vuln in vulns:
            cve = None
            for alias in vuln.get("aliases") or []:
                if str(alias).startswith("CVE-"):
                    cve = str(alias)
                    break
            if not cve or cve in seen:
                continue
            seen.add(cve)
            lib.setdefault("vulnerabilities", []).append(
                {
                    "below": "unknown",
                    "cve": cve,
                    "severity": "medium",
                    "note": (vuln.get("summary") or "")[:200],
                    "source": "osv",
                }
            )
        print(f"Merged {len(seen)} OSV entries for {key}")
    db["updated"] = __import__("datetime").date.today().isoformat()
    db["osv_merged"] = True
    if not dry_run:
        _USER.parent.mkdir(parents=True, exist_ok=True)
        _USER.write_text(json.dumps(db, indent=2) + "\n", encoding="utf-8")
        print(f"Updated: {_USER}")
    return db


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge OSV advisories into APEX CVE DB")
    parser.add_argument("--dry-run", action="store_true", help="fetch only; do not write ~/.apex")
    args = parser.parse_args()
    path = _USER if _USER.is_file() else _BUNDLE
    db = json.loads(path.read_text(encoding="utf-8"))
    merge_osv_into_db(db, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
