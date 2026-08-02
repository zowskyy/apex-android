"""bundletool provider for AAB/APKS workflows."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from apex.analysis import ApexError, sanitized_zip_name, sha256_file

from .registry import get_bundletool_command
from .runner import run_tool


def inspect_bundle(aab_path: Path) -> dict[str, Any]:
    command = get_bundletool_command()
    if not command:
        return {
            "status": "unavailable",
            "provider": "bundletool",
            "reason": "bundletool not configured (set APEX_BUNDLETOOL_JAR)",
        }
    result = run_tool(
        [*command, "dump", "manifest", "--bundle", str(aab_path)],
        timeout=180,
    )
    return {
        "status": "ok" if result.returncode == 0 else "error",
        "provider": "bundletool",
        "manifest": result.stdout[-20000:],
        "error": result.stderr[-2000:] if result.returncode else None,
    }


def build_apks(
    aab_path: Path,
    output_apks: Path,
    *,
    mode: str = "universal",
    keystore: Path | None = None,
    ks_pass: str | None = None,
    key_pass: str | None = None,
) -> dict[str, Any]:
    command = get_bundletool_command()
    if not command:
        raise ApexError("bundletool not configured; set APEX_BUNDLETOOL_JAR")
    argv = [
        *command,
        "build-apks",
        f"--bundle={aab_path}",
        f"--output={output_apks}",
        f"--mode={mode}",
    ]
    if keystore:
        if not ks_pass:
            raise ApexError("keystore password required for signed APKS output")
        argv.extend(
            [
                f"--ks={keystore}",
                f"--ks-pass=pass:{ks_pass}",
            ]
        )
        if key_pass:
            argv.append(f"--key-pass=pass:{key_pass}")
    result = run_tool(argv, timeout=600)
    if result.returncode:
        raise ApexError(f"bundletool build-apks failed:\n{(result.stdout + result.stderr)[-3000:]}")
    return {
        "provider": "bundletool",
        "output": str(output_apks),
        "sha256": sha256_file(output_apks),
        "mode": mode,
    }


def extract_apks(apks_path: Path, out_dir: Path) -> dict[str, Any]:
    apks_path, out_dir = Path(apks_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(apks_path) as archive:
        for name in archive.namelist():
            safe = sanitized_zip_name(name)
            if not safe or not safe.endswith(".apk"):
                continue
            destination = out_dir / safe
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            extracted.append(safe)
    return {"provider": "bundletool", "extracted": extracted, "out_dir": str(out_dir)}
