"""Run hard-gate scanners and produce a weighted GateReport."""

from __future__ import annotations

import json
from pathlib import Path

from apex.analysis import ApexError, resolve_android_package, sha256_file
from apex.gate.models import GateFinding, GateReport, GateStage, GateStatus
from apex.gate.scanners.dex_watch import scan_dex_watch
from apex.gate.scanners.native import scan_native
from apex.gate.scanners.secrets import scan_secrets
from apex.gate.scanners.static import scan_dex, scan_manifest, scan_security
from apex.gate.weights import load_scanner_weights

_STAGE_MIN_SCORE: dict[GateStage, float] = {
    "candidate": 60.0,
    "rc": 85.0,
    "beta": 95.0,
    "production": 100.0,
}


def _scanner_score(findings: list[GateFinding], scanner: str) -> float:
    scoped = [f for f in findings if f.scanner == scanner]
    if not scoped:
        return 100.0
    if any(f.status == GateStatus.FAIL for f in scoped):
        return 0.0
    if any(f.status == GateStatus.WARN for f in scoped):
        return 70.0
    return 100.0


def _weighted_score(findings: list[GateFinding], weights: dict[str, float]) -> float:
    total = 0.0
    for scanner, weight in weights.items():
        total += weight * _scanner_score(findings, scanner)
    return total


def run_hard_gate(
    apk_path: Path,
    *,
    msv: int = 28,
    stage: GateStage = "candidate",
    workspace: Path | None = None,
    weights_path: Path | None = None,
) -> GateReport:
    """Execute static hard gates on an APK or nested container."""
    source = Path(apk_path)
    if not source.is_file():
        raise ApexError(f"package not found: {source}")

    weights = load_scanner_weights(weights_path)
    work = workspace or source.parent
    resolved, container = resolve_android_package(source, work)
    findings: list[GateFinding] = []
    findings.extend(scan_manifest(resolved, msv))
    findings.extend(scan_dex(resolved))
    findings.extend(scan_security(resolved))
    findings.extend(scan_secrets(resolved))
    findings.extend(scan_native(resolved))
    findings.extend(scan_dex_watch(resolved))

    score = _weighted_score(findings, weights)
    blocking = [
        f"{f.scanner}:{f.category}: {f.message}"
        for f in findings
        if f.status == GateStatus.FAIL
    ]
    min_score = _STAGE_MIN_SCORE.get(stage, 60.0)
    gate_passed = not blocking and score >= min_score

    return GateReport(
        apk=str(resolved.resolve()),
        apk_sha256=sha256_file(resolved),
        stage=stage,
        gate_passed=gate_passed,
        score=score,
        msv_required=msv,
        findings=findings,
        blocking=blocking,
        container_note=str(container.get("container_note") or ""),
        resolved_from=container.get("resolved_from"),
    )


def write_gate_report(report: GateReport, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    payload["weights"] = load_scanner_weights()
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path
