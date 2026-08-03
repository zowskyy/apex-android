"""Hard-gate API watch scanner (crypto + reflection watchlists)."""

from __future__ import annotations

from pathlib import Path

from apex.api_watch import scan_apk_api_watch
from apex.gate.models import Confidence, GateFinding, GateStatus, normalize_status
from apex.gate.scanners.watchlists.crypto import CRYPTO_WATCHLIST
from apex.gate.scanners.watchlists.reflection import REFLECTION_WATCHLIST

_COMBINED = CRYPTO_WATCHLIST + REFLECTION_WATCHLIST


def scan_api_watch(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_apk_api_watch(apk_path, _COMBINED)
    if not raw:
        findings.append(
            GateFinding(
                scanner="api_watch",
                status=GateStatus.PASS,
                category="api-watch-clean",
                message="No API watchlist hits in DEX graph",
            )
        )
        return findings

    for item in raw[:20]:
        severity = str(item.get("severity", "warn")).lower()
        message = str(item.get("message", ""))
        confidence: Confidence = "MEDIUM"
        if "string-pool hint only" in message:
            confidence = "LOW"
        status = GateStatus.WARN
        if severity == "critical":
            status = normalize_status(GateStatus.FAIL, confidence)
        findings.append(
            GateFinding(
                scanner="api_watch",
                status=status,
                category=str(item.get("category", "api-watch")),
                message=message,
                evidence=str(item.get("evidence", "")),
                confidence=confidence,
                remediation="Review call sites and replace weak primitives where possible",
            )
        )
    return findings
