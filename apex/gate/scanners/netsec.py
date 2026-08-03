"""Hard-gate network security config scanner."""

from __future__ import annotations

from pathlib import Path

from apex.gate.models import GateFinding, GateStatus
from apex.netsec_scan import scan_network_security


def scan_netsec(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_network_security(apk_path)
    if not raw:
        findings.append(
            GateFinding(
                scanner="netsec",
                status=GateStatus.PASS,
                category="netsec-clean",
                message="No network security config issues detected",
            )
        )
        return findings

    for item in raw:
        severity = str(item.get("severity", "medium")).lower()
        category = str(item.get("category", "netsec"))
        remediation = ""
        if category == "netsec-user-ca":
            remediation = "Remove user CA trust or pin certificates for sensitive endpoints"
        elif "cleartext" in category:
            remediation = "Disable cleartext or restrict to debug builds"
        status = GateStatus.WARN
        if severity in {"critical", "high"} and category == "netsec-user-ca":
            status = GateStatus.WARN
        findings.append(
            GateFinding(
                scanner="netsec",
                status=status,
                category=category,
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
                confidence="HIGH" if severity in {"critical", "high"} else "MEDIUM",
                remediation=remediation,
            )
        )
    return findings
