"""Corpus statistics helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import CorpusStore


def corpus_stats(db_path: Path, *, serial: str | None = None) -> dict[str, Any]:
    store = CorpusStore(db_path)
    device_id = None
    if serial:
        row = store.conn.execute("SELECT id FROM devices WHERE serial = ?", (serial,)).fetchone()
        device_id = int(row["id"]) if row else None
    return {"serial": serial, **store.stats(device_id=device_id)}


def corpus_packages(db_path: Path, *, serial: str | None = None) -> list[dict[str, Any]]:
    store = CorpusStore(db_path)
    return store.packages(serial=serial)
