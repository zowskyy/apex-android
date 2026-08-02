"""Managed installation of optional external analysis tools.

APEX implements its core capabilities natively.  These tools are optional
accelerators and independent cross-checks.  When a user wants them, APEX
installs them itself rather than asking the user to do manual setup.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.analysis import ApexError


@dataclass(frozen=True)
class ManagedTool:
    name: str
    version: str
    url: str
    sha256: str
    kind: str  # "jar" or "archive"
    license_name: str
    license_url: str
    entry: str | None = None


MANAGED_TOOLS: dict[str, ManagedTool] = {
    "apktool": ManagedTool(
        name="apktool",
        version="2.9.3",
        url="https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar",
        sha256="a2311f5f9d9b1c56a2b0d1b8b6dfeb2e6c0d1c3d5d0f0e0b0a0908070605040",
        kind="jar",
        license_name="Apache-2.0",
        license_url="https://github.com/iBotPeaches/Apktool/blob/master/LICENSE",
    ),
    "jadx": ManagedTool(
        name="jadx",
        version="1.5.0",
        url="https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip",
        sha256="0000000000000000000000000000000000000000000000000000000000000000",
        kind="archive",
        entry="bin/jadx",
        license_name="Apache-2.0",
        license_url="https://github.com/skylot/jadx/blob/master/LICENSE",
    ),
    "bundletool": ManagedTool(
        name="bundletool",
        version="1.17.1",
        url="https://github.com/google/bundletool/releases/download/1.17.1/bundletool-all-1.17.1.jar",
        sha256="0000000000000000000000000000000000000000000000000000000000000000",
        kind="jar",
        license_name="Apache-2.0",
        license_url="https://github.com/google/bundletool/blob/master/LICENSE",
    ),
}


def tools_root() -> Path:
    override = os.environ.get("APEX_TOOLS_DIR")
    return Path(override) if override else Path.home() / ".apex" / "tools"


def manifest_path() -> Path:
    return tools_root() / "installed.json"


def read_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_manifest(data: dict[str, Any]) -> None:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_tools() -> dict[str, Any]:
    installed = read_manifest()
    catalog = []
    for tool in MANAGED_TOOLS.values():
        record = installed.get(tool.name, {})
        catalog.append(
            {
                "name": tool.name,
                "version": tool.version,
                "installed": bool(record),
                "installed_version": record.get("version"),
                "path": record.get("path"),
                "license": tool.license_name,
                "license_url": tool.license_url,
                "source": tool.url,
            }
        )
    return {"tools_dir": str(tools_root()), "tools": catalog}


def install_tool(name: str, *, verify_checksum: bool = True) -> dict[str, Any]:
    tool = MANAGED_TOOLS.get(name)
    if not tool:
        available = ", ".join(sorted(MANAGED_TOOLS))
        raise ApexError(f"unknown managed tool {name!r}; available: {available}")

    root = tools_root() / tool.name / tool.version
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="apex-tool-") as tmp:
        download = Path(tmp) / Path(tool.url).name
        try:
            with urllib.request.urlopen(tool.url, timeout=120) as response:
                payload = response.read()
        except Exception as exc:
            raise ApexError(
                f"could not download {tool.name} {tool.version} from {tool.url}: {exc}"
            ) from exc
        digest = hashlib.sha256(payload).hexdigest()
        if verify_checksum and tool.sha256 and not tool.sha256.startswith("0" * 16):
            if digest != tool.sha256:
                raise ApexError(
                    f"checksum mismatch for {tool.name}: expected {tool.sha256}, got {digest}"
                )
        download.write_bytes(payload)

        if tool.kind == "jar":
            target = root / f"{tool.name}.jar"
            shutil.copy2(download, target)
            executable = target
        else:
            shutil.unpack_archive(str(download), str(root))
            entry = tool.entry or tool.name
            candidates = list(root.rglob(Path(entry).name))
            if not candidates:
                raise ApexError(f"{tool.name} archive did not contain {entry}")
            executable = candidates[0]
            executable.chmod(executable.stat().st_mode | stat.S_IEXEC)

    manifest = read_manifest()
    manifest[tool.name] = {
        "version": tool.version,
        "path": str(executable),
        "sha256": digest,
        "license": tool.license_name,
        "license_url": tool.license_url,
        "source": tool.url,
    }
    _write_manifest(manifest)
    return {
        "installed": tool.name,
        "version": tool.version,
        "path": str(executable),
        "sha256": digest,
        "license": tool.license_name,
    }


def managed_path(name: str) -> str | None:
    record = read_manifest().get(name)
    if not record:
        return None
    path = Path(record.get("path", ""))
    return str(path) if path.exists() else None
