"""ADB subprocess wrapper for connected-device workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.analysis import ApexError, sanitized_zip_name
from apex.providers.registry import get_adb_command
from apex.providers.runner import run_tool


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str
    model: str | None = None
    product: str | None = None


@dataclass(frozen=True)
class DevicePackage:
    package: str
    apk_path: str
    system: bool = False


def _adb(argv: list[str], *, serial: str | None = None, timeout: int = 120) -> str:
    command = get_adb_command()
    if not command:
        raise ApexError("adb not found; install Android platform-tools or set APEX_ADB")
    prefix = [*command]
    if serial:
        prefix.extend(["-s", serial])
    result = run_tool([*prefix, *argv], timeout=timeout)
    if result.returncode:
        raise ApexError((result.stdout + result.stderr)[-2000:])
    return result.stdout


def list_devices() -> list[DeviceInfo]:
    command = get_adb_command()
    if not command:
        return []
    result = run_tool([*command, "devices", "-l"], timeout=30)
    devices: list[DeviceInfo] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = None
        product = None
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token.split(":", 1)[1]
            if token.startswith("product:"):
                product = token.split(":", 1)[1]
        devices.append(DeviceInfo(serial=serial, state=state, model=model, product=product))
    return devices


def list_packages(serial: str, *, user_id: int = 0) -> list[DevicePackage]:
    output = _adb(["shell", "pm", "list", "packages", "-f", "--user", str(user_id)], serial=serial)
    packages: list[DevicePackage] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        match = re.match(r"package:(.+)=(.+)", line)
        if not match:
            continue
        apk_path, package = match.groups()
        packages.append(
            DevicePackage(
                package=package,
                apk_path=apk_path,
                system=apk_path.startswith("/system/") or apk_path.startswith("/product/"),
            )
        )
    return packages


def package_paths(serial: str, package: str, *, user_id: int = 0) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise ApexError(f"invalid package name: {package}")
    output = _adb(
        ["shell", "pm", "path", package, "--user", str(user_id)],
        serial=serial,
    )
    paths = []
    for line in output.splitlines():
        if line.startswith("package:"):
            paths.append(line.split(":", 1)[1].strip())
    return paths


def dumpsys_package(serial: str, package: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise ApexError(f"invalid package name: {package}")
    return _adb(["shell", "dumpsys", "package", package], serial=serial, timeout=180)


def pull_path(serial: str, remote_path: str, destination: Path) -> Path:
    if not remote_path.startswith("/"):
        raise ApexError(f"remote path must be absolute: {remote_path}")
    safe_name = sanitized_zip_name(Path(remote_path).name)
    if not safe_name:
        raise ApexError(f"unsafe remote filename: {remote_path}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _adb(["pull", remote_path, str(destination)], serial=serial, timeout=300)
    return destination


def pull_package(
    serial: str,
    package: str,
    destination: Path,
    *,
    user_id: int = 0,
) -> dict[str, Any]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    paths = package_paths(serial, package, user_id=user_id)
    if not paths:
        raise ApexError(f"package not found on device: {package}")
    pulled: list[dict[str, str]] = []
    for index, remote in enumerate(paths):
        name = "base.apk" if index == 0 else f"split_{index}.apk"
        local = destination / name
        pull_path(serial, remote, local)
        pulled.append({"remote": remote, "local": str(local), "split": name})
    return {"package": package, "user_id": user_id, "artifacts": pulled}
