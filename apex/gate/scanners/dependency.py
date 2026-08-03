"""Hard-gate dependency/CVE advisory scanner (never FAIL by default)."""

from __future__ import annotations

from pathlib import Path

from apex.dependency_scan import scan_apk_dependencies
from apex.gate.models import Confidence, GateFinding, GateStatus, normalize_status


def scan_dependency(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_apk_dependencies(apk_path)
    if not raw:
        findings.append(
            GateFinding(
                scanner="dependency",
                status=GateStatus.PASS,
                category="dependency-clean",
                message="No bundled-library CVE signals in curated DB",
            )
        )
        return findings

    for item in raw:
        severity = str(item.get("severity", "info")).lower()
        confidence = str(item.get("confidence", "prefix-only"))
        conf: Confidence = "LOW"
        if confidence == "version-confirmed":
            conf = "HIGH"
        elif severity in {"high", "medium"}:
            conf = "MEDIUM"
        # Advisory scanner — never block gate; LOW prefix-only stays WARN.
        status = GateStatus.WARN
        if severity in {"high", "medium"} and conf == "HIGH":
            status = normalize_status(GateStatus.WARN, conf)
        findings.append(
            GateFinding(
                scanner="dependency",
                status=status,
                category=str(item.get("category", "dependency")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
                confidence=conf,
                remediation="Upgrade library or verify CVE applicability for your usage",
            )
        )
    return findings
