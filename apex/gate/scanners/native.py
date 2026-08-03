"""Hard-gate native ELF scanner (Slice S-1 / NATIVE prelude)."""

from __future__ import annotations

from pathlib import Path

from apex.gate.models import GateFinding, GateStatus
from apex.native_scan import scan_apk_native_libs


def scan_native(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raw = scan_apk_native_libs(apk_path)
    high = [item for item in raw if item.get("severity") == "high"]

    if any(item.get("category") == "native-exec-stack" for item in raw):
        findings.append(
            GateFinding(
                scanner="native",
                status=GateStatus.FAIL,
                category="native-exec-stack",
                message="Native library with executable stack segment",
                evidence=str(len(high)),
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

    for item in raw[:15]:
        severity = str(item.get("severity", "medium")).lower()
        if severity == "critical":
            status = GateStatus.FAIL
        elif severity in {"high", "medium"}:
            status = GateStatus.WARN
        else:
            continue
        findings.append(
            GateFinding(
                scanner="native",
                status=status,
                category=str(item.get("category", "native")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
            )
        )
    return findings
