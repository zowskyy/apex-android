"""Hard-gate native ELF scanner (Slice S-1 / NATIVE)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from apex.gate.models import Confidence, GateFinding, GateStatus, normalize_status
from apex.native_scan import scan_apk_native_libs

_Severity = Literal["critical", "high", "medium", "low", "info"]


def _status_for_severity(severity: str, min_sdk: int | None) -> GateStatus:
    sev = severity.lower()
    if sev == "critical":
        return GateStatus.FAIL
    if sev == "high":
        if min_sdk is not None and min_sdk >= 35:
            return GateStatus.FAIL
        return GateStatus.WARN
    if sev in {"high", "medium"}:
        return GateStatus.WARN
    return GateStatus.WARN


def scan_native(apk_path: Path, *, min_sdk: int | None = None) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_apk_native_libs(apk_path, min_sdk=min_sdk)
    high = [item for item in raw if item.get("severity") in {"critical", "high"}]

    if any(item.get("category") == "native-exec-stack" for item in raw):
        findings.append(
            GateFinding(
                scanner="native",
                status=GateStatus.FAIL,
                category="native-exec-stack",
                message="Native library with executable stack segment",
                evidence=str(len(high)),
                confidence="HIGH",
                remediation="Rebuild with -Wl,-z,noexecstack",
            )
        )
    elif high:
        findings.append(
            GateFinding(
                scanner="native",
                status=GateStatus.WARN,
                category="native-high",
                message=f"{len(high)} native hardening warning(s)",
                evidence=str(len(high)),
                confidence="MEDIUM",
            )
        )
    else:
        findings.append(
            GateFinding(
                scanner="native",
                status=GateStatus.PASS,
                category="native-clean",
                message="No critical native ELF hardening issues",
            )
        )

    for item in raw[:20]:
        severity = str(item.get("severity", "medium")).lower()
        if severity in {"critical", "high", "medium", "low"}:
            raw_conf = str(item.get("confidence", "HIGH"))
            confidence: Confidence = (
                raw_conf if raw_conf in {"HIGH", "MEDIUM", "LOW"} else "HIGH"
            )
            status = normalize_status(
                _status_for_severity(severity, min_sdk),
                confidence,
            )
            findings.append(
                GateFinding(
                    scanner="native",
                    status=status,
                    category=str(item.get("category", "native")),
                    message=str(item.get("message", "")),
                    evidence=str(item.get("evidence", "")),
                    confidence=confidence,
                    remediation=str(item.get("remediation", "")),
                )
            )
    return findings
