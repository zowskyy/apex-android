"""Best-effort dependency fingerprinting (blueprint CVE-2)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from apex.api_watch import collect_apk_dex_index

_DB_PATH = Path(__file__).resolve().parent / "data" / "cve_db.json"
_USER_DB = Path.home() / ".apex" / "cve_db.json"


def _parse_version_tuple(raw: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in re.split(r"[.\-]", raw):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            break
    return tuple(parts)


def _version_below(found: str, below: str) -> bool:
    left = _parse_version_tuple(found)
    right = _parse_version_tuple(below)
    if not left or not right:
        return False
    length = max(len(left), len(right))
    left = left + (0,) * (length - len(left))
    right = right + (0,) * (length - len(right))
    return left < right


def load_cve_db() -> dict[str, Any]:
    path = _USER_DB if _USER_DB.is_file() else _DB_PATH
    if not path.is_file():
        return {"libraries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def update_cve_db_from_bundle() -> Path:
    """Copy bundled DB to user cache (offline update-db no-op success)."""
    _USER_DB.parent.mkdir(parents=True, exist_ok=True)
    if _DB_PATH.is_file():
        _USER_DB.write_text(_DB_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return _USER_DB


def scan_apk_dependencies(apk_path: Path) -> list[dict[str, Any]]:
    apk_path = Path(apk_path)
    db = load_cve_db()
    index = collect_apk_dex_index(apk_path, lightweight=True)
    class_names = [str(c.get("name", "")) for c in index.get("classes") or []]
    strings = "\n".join(str(s) for s in index.get("strings") or [])
    findings: list[dict[str, Any]] = []

    for lib in db.get("libraries") or []:
        prefix = str(lib.get("package_prefix", ""))
        if not prefix:
            continue
        matched = [name for name in class_names if name.startswith(prefix)]
        if not matched:
            continue
        version = ""
        confidence = "prefix-only"
        version_regex = lib.get("version_regex")
        if version_regex:
            match = re.search(str(version_regex), strings)
            if match:
                version = match.group(1)
                confidence = "version-confirmed"
        for vuln in lib.get("vulnerabilities") or []:
            below = str(vuln.get("below", ""))
            if version and below and _version_below(version, below):
                findings.append(
                    {
                        "severity": str(vuln.get("severity", "medium")),
                        "category": "dependency-cve",
                        "message": f"{lib.get('name', prefix)} {version} below {below} ({vuln.get('cve', '')})",
                        "evidence": f"{confidence}: {prefix}",
                        "confidence": confidence,
                    }
                )
            elif not version and vuln.get("cve"):
                findings.append(
                    {
                        "severity": "info",
                        "category": "dependency-prefix",
                        "message": f"{lib.get('name', prefix)} detected — version unknown, manual CVE review",
                        "evidence": prefix,
                        "confidence": "prefix-only",
                    }
                )
    return findings
