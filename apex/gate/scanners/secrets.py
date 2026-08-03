"""Hard-gate secret/credential scanner (Slice 1 extension)."""

from __future__ import annotations

from pathlib import Path

from apex.gate.models import GateFinding, GateStatus
from apex.secrets_scan import scan_apk_secrets


def scan_secrets(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_apk_secrets(apk_path)
    critical = sum(1 for item in raw if item.get("severity") == "critical")
    high = sum(1 for item in raw if item.get("severity") == "high")

    if critical:
        findings.append(
            GateFinding(
                scanner="secrets",
                status=GateStatus.FAIL,
                category="secret-critical",
                message=f"{critical} critical secret/credential pattern(s)",
                evidence=str(critical),
            )
        )
    elif high:
        findings.append(
            GateFinding(
                scanner="secrets",
                status=GateStatus.WARN,
                category="secret-high",
                message=f"{high} high-confidence secret pattern(s)",
                evidence=str(high),
            )
        )
    else:
        findings.append(
            GateFinding(
                scanner="secrets",
                status=GateStatus.PASS,
                category="secrets-clean",
                message="No secret/credential patterns in scanned text assets",
            )
        )

    for item in raw[:15]:
        severity = str(item.get("severity", "info")).lower()
        status = GateStatus.FAIL if severity == "critical" else GateStatus.WARN
        if severity in {"low", "info"}:
            continue
        findings.append(
            GateFinding(
                scanner="secrets",
                status=status,
                category=str(item.get("category", "secret")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
            )
        )
    return findings
