"""Generate compliance artifacts from gate audit logs."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apex.gate.audit_log import AuditLogger, _audit_dir

_DEFAULT_OUT = _audit_dir() / "compliance"


def _utc_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _attestation_hmac(payload: str) -> str | None:
    key = os.environ.get("APEX_AUDIT_KEY") or os.environ.get("APEX_COMPLIANCE_KEY")
    if not key:
        return None
    return hashlib.sha256(f"{key}:{payload}".encode("utf-8")).hexdigest()


def generate_compliance_report(
    *,
    month: str | None = None,
    log_path: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Build monthly metrics + optional signed attestation from audit JSONL."""
    logger = AuditLogger(log_path=log_path or AuditLogger().log_path)
    ok, integrity_msg = logger.verify_integrity()
    target_month = month or _utc_month()
    out_root = out_dir or _DEFAULT_OUT
    out_root.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    if logger.log_path.is_file():
        for line in logger.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            ts = str(entry.get("ts") or "")
            if not ts.startswith(target_month):
                continue
            runs.append(entry)
            if not entry.get("gate_passed"):
                incidents.append(
                    {
                        "ts": ts,
                        "apk_sha256": entry.get("apk_sha256"),
                        "stage": entry.get("stage"),
                        "score": entry.get("score"),
                        "blocking_count": entry.get("blocking_count"),
                    }
                )

    total = len(runs)
    passed = sum(1 for r in runs if r.get("gate_passed"))
    failure_rate = (total - passed) / total if total else 0.0

    report: dict[str, Any] = {
        "schema_version": 1,
        "month": target_month,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_integrity_ok": ok,
        "audit_integrity_detail": integrity_msg,
        "metrics": {
            "gate_runs": total,
            "gate_passed": passed,
            "gate_failed": total - passed,
            "failure_rate": round(failure_rate, 4),
            "recent_failure_rate": round(logger.failure_rate(), 4),
        },
        "incidents": incidents,
        "kpis": {
            "gate_failure_rate_target": 0.02,
            "mttr_hours_target": 24,
            "unsigned_releases_target": 0,
            "audit_integrity_target": 1.0,
        },
    }

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    attestation = _attestation_hmac(canonical)
    if attestation:
        report["attestation_hmac"] = attestation

    out_path = out_root / f"compliance-{target_month}.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["output_path"] = str(out_path)
    return report


class ComplianceReporter:
    """Convenience wrapper for monthly report generation."""

    def __init__(self, log_path: Path | None = None, out_dir: Path | None = None) -> None:
        self.log_path = log_path
        self.out_dir = out_dir

    def monthly(self, month: str | None = None) -> dict[str, Any]:
        return generate_compliance_report(month=month, log_path=self.log_path, out_dir=self.out_dir)
