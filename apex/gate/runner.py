"""Run hard-gate scanners and produce a weighted GateReport."""

from __future__ import annotations

import json
from pathlib import Path

from apex.analysis import ApexError, inspect_apk, resolve_android_package, sha256_file
from apex.gate.budgets import run_with_budget
from apex.gate.models import GateFinding, GateReport, GateStage, GateStatus
from apex.gate.scanners.api_watch import scan_api_watch
from apex.gate.scanners.dependency import scan_dependency
from apex.gate.scanners.lint import scan_lint
from apex.gate.scanners.native import scan_native
from apex.gate.scanners.netsec import scan_netsec
from apex.gate.scanners.obfuscation import scan_obfuscation
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


def _manifest_min_sdk(apk_path: Path) -> int | None:
    inspected = inspect_apk(apk_path)
    manifest = inspected.get("manifest") or {}
    raw = str(manifest.get("min_sdk") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


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
    min_sdk = _manifest_min_sdk(resolved)
    findings: list[GateFinding] = []

    findings.extend(
        run_with_budget("manifest", lambda: scan_manifest(resolved, msv))
    )
    findings.extend(
        run_with_budget("dex", lambda: scan_dex(resolved))
    )
    findings.extend(
        run_with_budget("security", lambda: scan_security(resolved))
    )
    findings.extend(
        run_with_budget("secrets", lambda: scan_secrets(resolved))
    )
    findings.extend(
        run_with_budget("native", lambda: scan_native(resolved, min_sdk=min_sdk))
    )
    findings.extend(
        run_with_budget(
            "api_watch",
            lambda: scan_api_watch(resolved),
            fallback=lambda: scan_api_watch_light(resolved),
        )
    )
    findings.extend(
        run_with_budget("netsec", lambda: scan_netsec(resolved))
    )
    findings.extend(
        run_with_budget("lint", lambda: scan_lint(resolved, work))
    )
    findings.extend(
        run_with_budget("obfuscation", lambda: scan_obfuscation(resolved))
    )
    findings.extend(
        run_with_budget("dependency", lambda: scan_dependency(resolved))
    )

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


def scan_api_watch_light(apk_path: Path) -> list[GateFinding]:
    """Budget fallback: string-pool hints only (no xref graph)."""
    from apex.api_watch import collect_apk_dex_index, scan_watchlist
    from apex.gate.models import GateFinding, GateStatus
    from apex.gate.scanners.watchlists.crypto import CRYPTO_WATCHLIST
    from apex.gate.scanners.watchlists.reflection import REFLECTION_WATCHLIST

    index = collect_apk_dex_index(apk_path, lightweight=True)
    index["edges"] = []
    raw = scan_watchlist(index, CRYPTO_WATCHLIST + REFLECTION_WATCHLIST)
    if not raw:
        return [
            GateFinding(
                scanner="api_watch",
                status=GateStatus.PASS,
                category="api-watch-clean",
                message="No API watchlist hits (lightweight tier)",
            )
        ]
    findings: list[GateFinding] = []
    for item in raw[:15]:
        findings.append(
            GateFinding(
                scanner="api_watch",
                status=GateStatus.WARN,
                category=str(item.get("category", "api-watch")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
                confidence="LOW",
            )
        )
    return findings


def write_gate_report(report: GateReport, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    payload["weights"] = load_scanner_weights()
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path
