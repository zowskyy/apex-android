"""Incremental device sync orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.analysis import sha256_file
from apex.corpus.store import CorpusStore

from .adb import dumpsys_package, list_devices, list_packages


def _parse_version(dumpsys: str) -> tuple[int, str]:
    version_code = 0
    version_name = "unknown"
    for line in dumpsys.splitlines():
        if "versionCode=" in line:
            match = line.split("versionCode=")[1].split()[0]
            try:
                version_code = int(match)
            except ValueError:
                pass
        if "versionName=" in line:
            version_name = line.split("versionName=")[1].strip()
    return version_code, version_name


def sync_device(
    serial: str,
    db_path: Path,
    *,
    user_id: int = 0,
    analyze_out: Path | None = None,
) -> dict[str, Any]:
    store = CorpusStore(db_path)
    device_id = store.upsert_device(serial)
    run_id = store.start_sync(device_id, user_id)
    changed = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    try:
        packages = list_packages(serial, user_id=user_id)
        for pkg in packages:
            try:
                dumpsys = dumpsys_package(serial, pkg.package)
                version_code, version_name = _parse_version(dumpsys)
                quick = f"{pkg.package}:{version_code}:{version_name}"
                if store.has_snapshot(device_id, user_id, pkg.package, quick):
                    skipped += 1
                    continue
                from .pull import pull_to_layout

                pulled = pull_to_layout(
                    serial,
                    pkg.package,
                    Path.home() / ".apex" / "devices",
                    user_id=user_id,
                    version_name=version_name,
                    version_code=version_code,
                )
                dest = Path(pulled.destination)
                base = dest / "base.apk"
                if not base.is_file():
                    raise RuntimeError("base.apk missing after pull")
                sha = sha256_file(base)
                store.register_artifact(sha, base.stat().st_size, str(base))
                report_dir = (analyze_out or Path.home() / ".apex" / "reports") / sha[:12]
                from apex.workflows import analyze_apk

                analyze_apk(base, report_dir)
                store.record_snapshot(
                    run_id,
                    device_id,
                    user_id,
                    pkg.package,
                    version_code,
                    version_name,
                    quick,
                    sha,
                    str(report_dir / "report.json"),
                )
                changed += 1
            except Exception as exc:
                errors.append({"package": pkg.package, "error": str(exc)})
        store.finish_sync(run_id, "ok" if not errors else "partial", errors=errors)
    except Exception as exc:
        store.finish_sync(run_id, "error", errors=[{"error": str(exc)}])
        raise
    return {
        "serial": serial,
        "user_id": user_id,
        "changed": changed,
        "skipped": skipped,
        "errors": errors,
        "sync_run_id": run_id,
    }


def list_connected() -> list[dict[str, Any]]:
    return [
        {
            "serial": item.serial,
            "state": item.state,
            "model": item.model,
            "product": item.product,
        }
        for item in list_devices()
    ]
