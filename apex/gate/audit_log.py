"""Immutable audit trail for hard-gate executions.

Each record is append-only JSONL with a hash chain (prev_hash → entry_hash).
Tampering breaks the chain; use verify_integrity() before compliance reports.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apex.gate.models import GateReport


def _audit_dir() -> Path:
    return Path(os.environ.get("APEX_AUDIT_DIR", str(Path.home() / ".apex" / "audit")))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditLogger:
    """Record gate runs; verify chain integrity; rotate old logs."""

    log_path: Path | None = None
    chain_head_path: Path | None = None

    def __post_init__(self) -> None:
        base = _audit_dir()
        self.log_path = Path(self.log_path or base / "gate_runs.jsonl")
        self.chain_head_path = Path(self.chain_head_path or base / "chain_head.json")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_chain_head(self) -> str:
        if not self.chain_head_path.is_file():
            return ""
        try:
            data = json.loads(self.chain_head_path.read_text(encoding="utf-8"))
            return str(data.get("entry_hash") or "")
        except (OSError, json.JSONDecodeError):
            return ""

    def _write_chain_head(self, entry_hash: str) -> None:
        self.chain_head_path.write_text(
            json.dumps({"entry_hash": entry_hash, "updated": _utc_now()}, indent=2) + "\n",
            encoding="utf-8",
        )

    def record_gate_run(
        self,
        report: GateReport,
        *,
        context: str = "local",
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Append one gate run; returns the stored entry (with hashes)."""
        prev_hash = self._read_chain_head()
        body: dict[str, Any] = {
            "ts": _utc_now(),
            "context": context,
            "actor": actor or os.environ.get("APEX_AUDIT_ACTOR", "apex"),
            "apk": report.apk,
            "apk_sha256": report.apk_sha256,
            "stage": report.stage,
            "gate_passed": report.gate_passed,
            "score": round(report.score, 2),
            "blocking_count": len(report.blocking),
            "finding_count": len(report.findings),
            "prev_hash": prev_hash,
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        entry_hash = _sha256_hex(f"{prev_hash}:{canonical}")
        body["entry_hash"] = entry_hash

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, sort_keys=True) + "\n")

        self._write_chain_head(entry_hash)
        return body

    def verify_integrity(self) -> tuple[bool, str]:
        """Walk the log and validate hash chain."""
        if not self.log_path.is_file():
            return True, "empty log"
        prev = ""
        count = 0
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            stored_prev = str(entry.get("prev_hash") or "")
            if stored_prev != prev:
                return False, f"chain break at record {count + 1}: prev_hash mismatch"
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
            expected = _sha256_hex(f"{prev}:{canonical}")
            if entry.get("entry_hash") != expected:
                return False, f"hash mismatch at record {count + 1}"
            prev = str(entry.get("entry_hash") or "")
            count += 1
        return True, f"ok ({count} records)"

    def rotate_logs(self, *, keep_days: int = 30, compress: bool = True) -> Path | None:
        """Archive logs older than keep_days; returns archive path if created."""
        if not self.log_path.is_file():
            return None
        archive = self.log_path.parent / f"gate_runs.{datetime.now(timezone.utc):%Y%m%d}.jsonl"
        if archive.exists():
            return None
        self.log_path.rename(archive)
        if compress:
            import gzip

            gz = archive.with_suffix(".jsonl.gz")
            with archive.open("rb") as src, gzip.open(gz, "wb") as dst:
                dst.writelines(src)
            archive.unlink()
            return gz
        return archive

    def failure_rate(self, *, limit: int = 200) -> float:
        """Recent gate failure rate (0.0–1.0) for monitor-gates workflow."""
        if not self.log_path.is_file():
            return 0.0
        lines = [ln for ln in self.log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        sample = lines[-limit:]
        if not sample:
            return 0.0
        fails = sum(1 for ln in sample if not json.loads(ln).get("gate_passed"))
        return fails / len(sample)


def immutable(log_path: Path) -> bool:
    """Return True if log passes integrity check."""
    ok, _ = AuditLogger(log_path=log_path).verify_integrity()
    return ok
