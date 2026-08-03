"""Obfuscation-applied check (blueprint XS-5)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from apex.api_watch import collect_apk_dex_index
from apex.gate.models import GateFinding, GateStatus

_SHORT_CLASS = re.compile(r"^[a-z](?:\.[a-z]){2,}$")


def scan_obfuscation(apk_path: Path) -> list[GateFinding]:
    apk_path = Path(apk_path)
    findings: list[GateFinding] = []

    has_mapping = False
    with zipfile.ZipFile(apk_path) as archive:
        for name in archive.namelist():
            low = name.lower()
            if "mapping.txt" in low or "proguard" in low and low.endswith(".txt"):
                has_mapping = True
                break

    index = collect_apk_dex_index(apk_path, lightweight=True)
    classes = [str(c.get("name", "")) for c in index.get("classes") or []]
    short_names = [name for name in classes if _SHORT_CLASS.match(name.split("$")[0])]
    ratio = len(short_names) / max(len(classes), 1)

    if has_mapping:
        findings.append(
            GateFinding(
                scanner="obfuscation",
                status=GateStatus.PASS,
                category="mapping-present",
                message="ProGuard/R8 mapping file present in package",
            )
        )
        return findings

    if ratio > 0.35 and len(classes) > 20:
        findings.append(
            GateFinding(
                scanner="obfuscation",
                status=GateStatus.WARN,
                category="obfuscation-missing",
                message=(
                    f"{len(short_names)} short obfuscated-style class names "
                    f"({ratio:.0%}) but no mapping file in APK"
                ),
                evidence=f"sample={short_names[:3]}",
            )
        )
    else:
        findings.append(
            GateFinding(
                scanner="obfuscation",
                status=GateStatus.PASS,
                category="obfuscation-ok",
                message="No sign of missing mapping for heavy obfuscation",
            )
        )
    return findings
