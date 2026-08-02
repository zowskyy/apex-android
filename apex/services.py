"""Shared application services for CLI and web interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.corpus.stats import corpus_stats
from apex.device.sync import list_connected, sync_device
from apex.workflows import (
    analyze_any,
    decompile_apk,
    doctor,
    export_bundle,
    export_icon,
    generate_sbom,
    privacy_report,
    scan_trackers,
)


class AnalysisService:
    def inspect_bundle(self, apk_path: Path, out_dir: Path) -> dict[str, Any]:
        return analyze_any(apk_path, out_dir)

    def decompile(self, apk_path: Path, out_dir: Path, *, provider: str = "auto") -> dict[str, Any]:
        return decompile_apk(apk_path, out_dir, provider=provider)


class IntelService:
    def trackers(self, path: Path) -> dict[str, Any]:
        return scan_trackers(path)

    def sbom(self, path: Path) -> dict[str, Any]:
        return generate_sbom(path)

    def privacy(self, path: Path) -> dict[str, Any]:
        return privacy_report(path)


class DeviceService:
    def list_devices(self) -> list[dict[str, Any]]:
        return list_connected()

    def sync(self, serial: str, db_path: Path, *, user_id: int = 0) -> dict[str, Any]:
        return sync_device(serial, db_path, user_id=user_id)


class CorpusService:
    def stats(self, db_path: Path, *, serial: str | None = None) -> dict[str, Any]:
        return corpus_stats(db_path, serial=serial)


class ExportService:
    def icon(self, apk_path: Path, output: Path) -> dict[str, Any]:
        return export_icon(apk_path, output)

    def bundle(self, apk_path: Path, out_dir: Path) -> dict[str, Any]:
        return export_bundle(apk_path, out_dir)


def health() -> dict[str, Any]:
    return doctor()
