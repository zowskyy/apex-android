"""Shared provider contracts and provenance helpers."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Generic, Literal, TypeVar

T = TypeVar("T")
ProviderStatus = Literal["ok", "fallback", "unavailable", "error"]


@dataclass(frozen=True)
class ProvenanceRecord:
    operation: str
    provider: str
    provider_version: str | None
    status: ProviderStatus
    duration_ms: int | None = None
    fallback_from: str | None = None
    reason: str | None = None


@dataclass
class ProviderResult(Generic[T]):
    data: T
    provenance: ProvenanceRecord


@dataclass
class ToolInfo:
    name: str
    status: Literal["ok", "missing", "error"]
    path: str | None = None
    version: str | None = None
    source: str | None = None
    install_hint: str | None = None


@dataclass
class ProvenanceCollector:
    records: list[ProvenanceRecord] = field(default_factory=list)

    def add(self, record: ProvenanceRecord) -> None:
        self.records.append(record)

    def extend(self, records: list[ProvenanceRecord]) -> None:
        self.records.extend(records)

    def as_list(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.records]


def attach_provenance(
    payload: dict[str, Any],
    collector: ProvenanceCollector,
    *,
    schema_version: int = 3,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["schema_version"] = schema_version
    enriched["provenance"] = collector.as_list()
    return enriched


class timed_operation:
    """Context manager that records elapsed time for a provenance entry."""

    def __init__(
        self,
        collector: ProvenanceCollector,
        operation: str,
        provider: str,
        provider_version: str | None = None,
        *,
        fallback_from: str | None = None,
    ):
        self.collector = collector
        self.operation = operation
        self.provider = provider
        self.provider_version = provider_version
        self.fallback_from = fallback_from
        self._start = 0.0
        self.status: ProviderStatus = "ok"
        self.reason: str | None = None

    def __enter__(self) -> timed_operation:
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, _tb) -> Literal[False]:
        duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc_type is not None:
            self.status = "error"
            self.reason = str(exc)
        self.collector.add(
            ProvenanceRecord(
                operation=self.operation,
                provider=self.provider,
                provider_version=self.provider_version,
                status=self.status,
                duration_ms=duration_ms,
                fallback_from=self.fallback_from,
                reason=self.reason,
            )
        )
        return False

    def mark_fallback(self, reason: str) -> None:
        self.status = "fallback"
        self.reason = reason

    def mark_unavailable(self, reason: str) -> None:
        self.status = "unavailable"
        self.reason = reason
