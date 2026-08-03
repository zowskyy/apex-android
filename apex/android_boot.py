"""Android entrypoint for embedded on-device APEX (Chaquopy / foreground service)."""

from __future__ import annotations

import json
import traceback
from pathlib import Path


def _write_status(workspace: Path, phase: str, detail: str = "", error: str = "") -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    payload = {"phase": phase, "detail": detail, "error": error}
    (workspace / "engine-status.json").write_text(json.dumps(payload), encoding="utf-8")


def prepare_engine(workspace: str, ram_mb: int = 0, cpu_cores: int = 0) -> dict[str, str]:
    """Import APEX + Androguard before binding the HTTP server (slow on first launch)."""
    workspace_path = Path(workspace)
    try:
        _write_status(workspace_path, "loading", "configuring device profile")
        from apex.device_profile import configure_device_profile

        configure_device_profile(ram_mb=int(ram_mb), cpu_cores=int(cpu_cores), engine_mode="on_device")

        _write_status(workspace_path, "loading", "importing apex")
        import apex  # noqa: F401

        _write_status(workspace_path, "loading", "importing androguard")
        import androguard  # noqa: F401

        _write_status(workspace_path, "loading", "validating parsers")
        from apex.engine_validate import validate_on_device_parsers

        validation = validate_on_device_parsers()
        if validation.get("ok") != "true":
            raise RuntimeError(validation.get("error", "parser validation failed"))

        _write_status(workspace_path, "ready", "imports complete")
        return {"ok": "true", "androguard": getattr(androguard, "__version__", "installed")}
    except Exception as exc:
        tb = traceback.format_exc()
        _write_status(workspace_path, "failed", str(exc), tb)
        return {"ok": "false", "error": str(exc), "trace": tb}


def serve_standalone(
    workspace: str,
    port: int = 8765,
    ram_mb: int = 0,
    cpu_cores: int = 0,
    remote_enhanced: bool = False,
) -> None:
    """Start the local web UI bound to localhost on the device."""
    from apex.device_profile import configure_device_profile
    from apex.web import serve

    workspace_path = Path(workspace)
    engine_mode = "remote_server" if remote_enhanced else "on_device"

    if not remote_enhanced:
        prep = prepare_engine(workspace, ram_mb, cpu_cores)
        if prep.get("ok") != "true":
            _write_status(workspace_path, "failed", prep.get("error", "prepare failed"))
            raise RuntimeError(prep.get("error", "APEX engine prepare failed"))

    configure_device_profile(
        ram_mb=int(ram_mb),
        cpu_cores=int(cpu_cores),
        engine_mode=engine_mode,
    )
    workspace_path.mkdir(parents=True, exist_ok=True)
    _write_status(workspace_path, "listening", f"http://127.0.0.1:{int(port)}")

    serve(
        host="127.0.0.1",
        port=int(port),
        workspace=workspace_path,
        open_browser=False,
        mobile=False,
        standalone=True,
        engine_mode=engine_mode,
    )
