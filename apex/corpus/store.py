"""SQLite-backed local device corpus index."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class CorpusStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def _migrate(self) -> None:
        schema = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
        self.conn.executescript(schema)
        self.conn.commit()

    def upsert_device(self, serial: str, *, model: str | None = None, sdk: int | None = None) -> int:
        now = int(time.time())
        self.conn.execute(
            """
            INSERT INTO devices(serial, model, sdk, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(serial) DO UPDATE SET
              model=COALESCE(excluded.model, devices.model),
              sdk=COALESCE(excluded.sdk, devices.sdk),
              last_seen_at=excluded.last_seen_at
            """,
            (serial, model, sdk, now),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM devices WHERE serial = ?", (serial,)).fetchone()
        return int(row["id"])

    def start_sync(self, device_id: int, user_id: int) -> int:
        now = int(time.time())
        cursor = self.conn.execute(
            "INSERT INTO sync_runs(device_id, user_id, started_at, status) VALUES (?, ?, ?, ?)",
            (device_id, user_id, now, "running"),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def finish_sync(
        self,
        run_id: int,
        status: str,
        *,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        self.conn.execute(
            "UPDATE sync_runs SET finished_at = ?, status = ?, error_json = ? WHERE id = ?",
            (int(time.time()), status, json.dumps(errors or []), run_id),
        )
        self.conn.commit()

    def has_snapshot(self, device_id: int, user_id: int, package: str, fingerprint: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM package_snapshots ps
            JOIN sync_runs sr ON sr.id = ps.sync_run_id
            WHERE sr.device_id = ? AND sr.user_id = ? AND ps.package_name = ?
              AND ps.quick_fingerprint = ? AND sr.status IN ('ok', 'partial')
            ORDER BY sr.finished_at DESC LIMIT 1
            """,
            (device_id, user_id, package, fingerprint),
        ).fetchone()
        return row is not None

    def register_artifact(self, sha256: str, size_bytes: int, local_path: str) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO artifacts(sha256, size_bytes, local_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (sha256, size_bytes, local_path, int(time.time())),
        )
        self.conn.commit()

    def record_snapshot(
        self,
        sync_run_id: int,
        device_id: int,
        user_id: int,
        package_name: str,
        version_code: int,
        version_name: str,
        fingerprint: str,
        artifact_sha256: str,
        report_path: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO package_snapshots(
              sync_run_id, package_name, version_code, version_name,
              quick_fingerprint, artifact_sha256, report_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sync_run_id,
                package_name,
                version_code,
                version_name,
                fingerprint,
                artifact_sha256,
                report_path,
            ),
        )
        self.conn.commit()

    def packages(self, *, serial: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT ps.package_name, ps.version_code, ps.version_name,
                   ps.artifact_sha256, ps.report_path, d.serial
            FROM package_snapshots ps
            JOIN sync_runs sr ON sr.id = ps.sync_run_id
            JOIN devices d ON d.id = sr.device_id
        """
        params: tuple[Any, ...] = ()
        if serial:
            query += " WHERE d.serial = ?"
            params = (serial,)
        query += " ORDER BY ps.package_name"
        return [dict(row) for row in self.conn.execute(query, params).fetchall()]

    def stats(self, *, device_id: int | None = None) -> dict[str, Any]:
        where = "WHERE sr.device_id = ?" if device_id else ""
        params: tuple[Any, ...] = (device_id,) if device_id else ()
        packages = self.conn.execute(
            f"""
            SELECT COUNT(DISTINCT ps.package_name) AS package_count,
                   COUNT(*) AS snapshot_count
            FROM package_snapshots ps
            JOIN sync_runs sr ON sr.id = ps.sync_run_id
            {where}
            """,
            params,
        ).fetchone()
        artifacts = self.conn.execute("SELECT COUNT(*) AS c FROM artifacts").fetchone()
        return {
            "package_count": packages["package_count"] if packages else 0,
            "snapshot_count": packages["snapshot_count"] if packages else 0,
            "artifact_count": artifacts["c"] if artifacts else 0,
        }
