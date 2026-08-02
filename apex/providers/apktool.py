"""apktool 3.x provider helpers."""

from __future__ import annotations

import re
from pathlib import Path

from apex.analysis import ApexError

from .runner import probe_version, resolve_apktool_command, run_tool


def apktool_version() -> str | None:
    command = resolve_apktool_command()
    if not command:
        return None
    return probe_version(command)


def ensure_apktool_compatible() -> list[str]:
    command = resolve_apktool_command()
    if not command:
        raise ApexError("apktool not found; install apktool 3.x or set APEX_APKTOOL_JAR")
    version = apktool_version() or ""
    major = int(version.split(".")[0]) if version and version[0].isdigit() else 0
    if major and major < 3:
        raise ApexError(
            f"apktool {version} is too old; APEX requires apktool 3.x (aapt2-only)"
        )
    return command


def decode_with_apktool(apk_path: Path, out_dir: Path) -> None:
    command = ensure_apktool_compatible()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    result = run_tool([*command, "d", "-f", str(apk_path), "-o", str(out_dir)], timeout=600)
    if result.returncode:
        raise ApexError(f"apktool decode failed:\n{(result.stdout + result.stderr)[-3000:]}")


def build_with_apktool(project_dir: Path, output_apk: Path) -> None:
    command = ensure_apktool_compatible()
    output_apk.parent.mkdir(parents=True, exist_ok=True)
    result = run_tool([*command, "b", str(project_dir), "-o", str(output_apk)], timeout=600)
    if result.returncode:
        raise ApexError(f"apktool build failed:\n{(result.stdout + result.stderr)[-3000:]}")


def framework_diagnostics(apk_path: Path, target_sdk: str) -> dict[str, object]:
    command = resolve_apktool_command()
    version = apktool_version()
    return {
        "apk": str(apk_path),
        "target_sdk": target_sdk,
        "apktool_available": command is not None,
        "apktool_version": version,
        "aapt2_only": bool(version and version.startswith("3")),
        "verdict": "READY" if command else "RAW_BACKEND_ONLY",
        "message": (
            "apktool 3.x is available for compiled-resource rebuilds"
            if command
            else "Install apktool 3.x or set APEX_APKTOOL_JAR for compiled-resource rebuilds"
        ),
    }
