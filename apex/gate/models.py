"""Hard-gate report models (Slice 0 foundation — no extra runtime deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


GateStage = Literal["candidate", "rc", "beta", "production"]


def normalize_status(status: GateStatus, confidence: Confidence) -> GateStatus:
    """LOW-confidence FAIL is downgraded to WARN (advisory scanners)."""
    if status == GateStatus.FAIL and confidence == "LOW":
        return GateStatus.WARN
    return status


@dataclass
class GateFinding:
    scanner: str
    status: GateStatus
    category: str
    message: str
    evidence: str = ""
    weight: float = 1.0
    confidence: Confidence = "HIGH"
    remediation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanner": self.scanner,
            "status": self.status.value,
            "category": self.category,
            "message": self.message,
            "evidence": self.evidence,
            "weight": self.weight,
            "confidence": self.confidence,
            "remediation": self.remediation,
        }


@dataclass
class GateReport:
    apk: str
    apk_sha256: str
    stage: GateStage
    gate_passed: bool
    score: float
    msv_required: int
    findings: list[GateFinding] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    container_note: str = ""
    resolved_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "apk": self.apk,
            "apk_sha256": self.apk_sha256,
            "stage": self.stage,
            "gate_passed": self.gate_passed,
            "score": round(self.score, 2),
            "msv_required": self.msv_required,
            "container_note": self.container_note,
            "resolved_from": self.resolved_from,
            "blocking": self.blocking,
            "findings": [item.to_dict() for item in self.findings],
        }
