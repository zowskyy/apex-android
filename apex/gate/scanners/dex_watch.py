"""DEX string-pool watchlist (reflection / crypto hints — SECRETS-2 + API prelude)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from apex.gate.models import GateFinding, GateStatus
from apex.secrets_scan import dex_string_pool

# String-level watchlist (full xref API-watch is a follow-up slice).
_STRING_WATCH: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "dex-class-loader",
        re.compile(r"dalvik\.system\.DexClassLoader|dalvik\.system\.PathClassLoader"),
        "WARN",
        "DexClassLoader / PathClassLoader referenced in DEX strings — review dynamic loading",
    ),
    (
        "reflection",
        re.compile(r"Ljava/lang/reflect/Method;|Ljava/lang/reflect/Class;"),
        "WARN",
        "Reflection types referenced in DEX strings — review invoke/forName usage",
    ),
    (
        "weak-crypto-ecb",
        re.compile(r"/ECB|DES/|RC4"),
        "WARN",
        "Weak crypto primitive name in DEX strings — verify Cipher configuration",
    ),
    (
        "weak-digest",
        re.compile(r"MD5|SHA-1|SHA1"),
        "WARN",
        "Legacy digest name in DEX strings — verify not used for security-sensitive hashing",
    ),
]


def scan_dex_watch(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    hits: list[tuple[str, str]] = []
    with zipfile.ZipFile(apk_path) as archive:
        dex_names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name.replace("\\", "/"))
        )
        for dex_name in dex_names:
            try:
                strings = dex_string_pool(archive.read(dex_name), dex_name)
            except Exception:
                continue
            blob = "\n".join(strings)
            for category, pattern, _severity, message in _STRING_WATCH:
                if pattern.search(blob):
                    hits.append((category, dex_name))

    if not hits:
        findings.append(
            GateFinding(
                scanner="dex_watch",
                status=GateStatus.PASS,
                category="dex-watch-clean",
                message="No high-risk API string hints in DEX pools",
            )
        )
        return findings

    messages = {category: message for category, _p, _s, message in _STRING_WATCH}
    for category, dex_name in hits[:12]:
        findings.append(
            GateFinding(
                scanner="dex_watch",
                status=GateStatus.WARN,
                category=category,
                message=messages.get(category, "DEX string watchlist hit"),
                evidence=dex_name,
            )
        )
    return findings
