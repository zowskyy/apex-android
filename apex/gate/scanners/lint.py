"""Hard-gate lint scanner (decompile + YAML rules)."""

from __future__ import annotations

from pathlib import Path

from apex.gate.models import GateFinding, GateStatus
from apex.lint_scan import scan_apk_lint


def scan_lint(apk_path: Path, workspace: Path | None = None) -> list[GateFinding]:
    findings: list[GateFinding] = []
    work = workspace or apk_path.parent
    raw = scan_apk_lint(apk_path, work)
    if not raw:
        findings.append(
            GateFinding(
                scanner="lint",
                status=GateStatus.PASS,
                category="lint-clean",
                message="No lint rule matches in decompiled sources",
            )
        )
        return findings

    for item in raw[:25]:
        severity = str(item.get("severity", "medium")).lower()
        status = GateStatus.WARN
        if severity == "high":
            status = GateStatus.WARN
        findings.append(
            GateFinding(
                scanner="lint",
                status=status,
                category=str(item.get("category", "lint")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
                confidence="HIGH" if severity == "high" else "MEDIUM",
                remediation="Fix decompiled-source pattern or document accepted risk",
            )
        )
    return findings
