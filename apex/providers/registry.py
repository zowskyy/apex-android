"""Provider discovery, capability resolution, and doctor reporting."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from apex.analysis import _native_zip
from apex.version import __version__

from .runner import (
    INSTALL_HINTS,
    resolve_apktool_command,
    resolve_executable,
    resolve_jar_command,
    resolve_java_command,
    probe_version,
    TOOL_ENV,
)
from .types import ToolInfo


CAPABILITY_ORDER: dict[str, list[str]] = {
    "archive.extract": ["rust", "python"],
    "manifest.decode": ["androguard"],
    "dex.index": ["androguard"],
    "decompile.java": ["jadx", "androguard"],
    "decode.resources": ["apktool", "raw"],
    "build.resources": ["apktool", "raw"],
    "verify.signatures": ["apksigner", "androguard"],
    "sign.apk": ["apksigner"],
    "bundle.build_apks": ["bundletool"],
    "bundle.dump_manifest": ["bundletool"],
    "benchmark.apkanalyzer": ["apkanalyzer"],
}


class ProviderRegistry:
    def preference(self, capability: str) -> list[str]:
        return list(CAPABILITY_ORDER.get(capability, []))

    def resolve(self, capability: str, *, requested: str = "auto") -> str | None:
        order = self.preference(capability)
        if requested != "auto":
            return requested if self.is_available(requested, capability) else None
        for provider in order:
            if self.is_available(provider, capability):
                return provider
        return None

    def is_available(self, provider: str, capability: str) -> bool:
        if provider == "rust":
            return capability.startswith("archive.") and _native_zip is not None
        if provider == "python":
            return capability.startswith("archive.")
        if provider == "androguard":
            return capability in {
                "manifest.decode",
                "dex.index",
                "decompile.java",
                "verify.signatures",
            }
        if provider == "raw":
            return capability in {"decode.resources", "build.resources"}
        if provider == "jadx":
            return get_jadx_command() is not None
        if provider == "apktool":
            return resolve_apktool_command() is not None
        if provider == "apksigner":
            return resolve_executable("apksigner", env_key=TOOL_ENV["apksigner"])[0] is not None
        if provider == "apkanalyzer":
            return resolve_executable("apkanalyzer", env_key=TOOL_ENV["apkanalyzer"])[0] is not None
        if provider == "bundletool":
            return resolve_jar_command(TOOL_ENV["bundletool"], "bundletool.jar") is not None
        return False


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def get_jadx_command() -> list[str] | None:
    executable, _ = resolve_executable("jadx", env_key=TOOL_ENV["jadx"])
    if executable:
        return [executable]
    jar = resolve_jar_command("APEX_JADX_JAR", "jadx.jar")
    return jar


def get_apksigner_command() -> list[str] | None:
    path, _ = resolve_executable("apksigner", env_key=TOOL_ENV["apksigner"])
    return [path] if path else None


def get_apkanalyzer_command() -> list[str] | None:
    path, _ = resolve_executable("apkanalyzer", env_key=TOOL_ENV["apkanalyzer"])
    return [path] if path else None


def get_bundletool_command() -> list[str] | None:
    return resolve_jar_command(TOOL_ENV["bundletool"], "bundletool.jar")


def get_adb_command() -> list[str] | None:
    path, _ = resolve_executable("adb", env_key=TOOL_ENV["adb"])
    return [path] if path else None


def tool_matrix() -> dict[str, ToolInfo]:
    tools: dict[str, ToolInfo] = {}

    java = resolve_java_command()
    tools["java"] = _tool_from_command("java", java)

    jadx = get_jadx_command()
    tools["jadx"] = _tool_from_command("jadx", jadx)

    apktool = resolve_apktool_command()
    tools["apktool"] = _tool_from_command("apktool", apktool)

    apksigner = get_apksigner_command()
    tools["apksigner"] = _tool_from_command("apksigner", apksigner)

    apkanalyzer = get_apkanalyzer_command()
    tools["apkanalyzer"] = _tool_from_command("apkanalyzer", apkanalyzer)

    bundletool = get_bundletool_command()
    tools["bundletool"] = _tool_from_command("bundletool", bundletool)

    adb = get_adb_command()
    tools["adb"] = _tool_from_command("adb", adb)

    aapt2_path, _ = resolve_executable("aapt2", env_key=TOOL_ENV["aapt2"])
    tools["aapt2"] = _tool_from_command("aapt2", [aapt2_path] if aapt2_path else None)

    try:
        import androguard

        version = getattr(androguard, "__version__", "installed")
        tools["androguard"] = ToolInfo("androguard", "ok", version=version, source="python")
    except ImportError:
        tools["androguard"] = ToolInfo(
            "androguard",
            "missing",
            install_hint="pip install androguard>=4.1.4",
        )

    tools["native_zip"] = ToolInfo(
        "native_zip",
        "ok" if _native_zip is not None else "missing",
        source="rust" if _native_zip is not None else None,
        install_hint=None if _native_zip is not None else "build apex_zip_reader extension",
    )
    return tools


def _tool_from_command(name: str, command: list[str] | None) -> ToolInfo:
    if not command:
        return ToolInfo(name, "missing", install_hint=INSTALL_HINTS.get(name))
    version = probe_version(command)
    return ToolInfo(name, "ok", path=command[0], version=version, source="resolved")


def capability_status() -> dict[str, dict[str, Any]]:
    registry = get_registry()
    result: dict[str, dict[str, Any]] = {}
    for capability, providers in CAPABILITY_ORDER.items():
        selected = registry.resolve(capability, requested="auto")
        if selected:
            result[capability] = {"status": "ready", "provider": selected}
        elif providers:
            result[capability] = {
                "status": "degraded" if providers[-1] == "androguard" else "unavailable",
                "provider": providers[-1] if providers[-1] == "androguard" else None,
            }
        else:
            result[capability] = {"status": "unavailable", "provider": None}
    return result


def doctor_report() -> dict[str, Any]:
    tools = tool_matrix()
    capabilities = capability_status()
    core_ready = tools["androguard"].status == "ok"
    return {
        "schema_version": 2,
        "apex": __version__,
        "ready": core_ready,
        "tools": {name: asdict(info) for name, info in tools.items()},
        "capabilities": capabilities,
    }
