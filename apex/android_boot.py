"""Android entrypoint for embedded on-device APEX (Chaquopy / foreground service)."""

from __future__ import annotations

from pathlib import Path


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

    engine_mode = "remote_server" if remote_enhanced else "on_device"
    configure_device_profile(ram_mb=int(ram_mb), cpu_cores=int(cpu_cores), engine_mode=engine_mode)

    workspace_path = Path(workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)

    serve(
        host="127.0.0.1",
        port=int(port),
        workspace=workspace_path,
        open_browser=False,
        mobile=False,
        standalone=True,
        engine_mode=engine_mode,
    )
