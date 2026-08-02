"""Device workflow models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PullResult:
    package: str
    destination: str
    artifact_count: int
