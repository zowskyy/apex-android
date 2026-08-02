"""Cheap preflight heuristics before expensive decompilation."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any


PACKER_HINTS = (
    ("assets/protect", "protector_assets"),
    ("libjiagu", "jiagu"),
    ("libsecexe", "secexe"),
    ("classes.dex", "standard_dex"),
)


def preflight_apk(apk_path: Path) -> dict[str, Any]:
    apk_path = Path(apk_path)
    findings: list[dict[str, str]] = []
    dex_count = 0
    with zipfile.ZipFile(apk_path) as archive:
        names = archive.namelist()
        lowered = [name.lower() for name in names]
        for needle, label in PACKER_HINTS:
            if any(needle in item for item in lowered):
                findings.append(
                    {
                        "category": "preflight",
                        "severity": "info",
                        "message": f"matched heuristic: {label}",
                        "evidence": needle,
                    }
                )
        dex_count = sum(1 for name in names if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name))
        if dex_count == 0:
            findings.append(
                {
                    "category": "preflight",
                    "severity": "warn",
                    "message": "no classes.dex found in archive",
                    "evidence": "dex-missing",
                }
            )
        for name in names:
            if name.endswith(".dex") and name.startswith("assets/"):
                findings.append(
                    {
                        "category": "preflight",
                        "severity": "review",
                        "message": "DEX file stored under assets/ (possible packer)",
                        "evidence": name,
                    }
                )
    recommendation = "proceed"
    if any(item["severity"] == "review" for item in findings):
        recommendation = "review_before_full_decompile"
    return {
        "dex_count": dex_count,
        "findings": findings,
        "recommendation": recommendation,
    }
