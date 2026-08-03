"""Adaptive performance limits for on-device APEX (phones/tablets).

Desktop and remote-server modes use the full limits. On-device mode scales
archive expansion, upload size, decompile depth, and UI class caps based on
reported RAM and CPU so APEX can run offline without pretending to match a PC.
"""

from __future__ import annotations

import os
import platform
from typing import Any

# Desktop / remote-server defaults (unchanged from analysis.py originals).
DESKTOP_LIMITS: dict[str, Any] = {
    "tier": "desktop",
    "engine_mode": "desktop",
    "max_entry_size": 512 * 1024 * 1024,
    "max_total_size": 2 * 1024 * 1024 * 1024,
    "max_entries": 200_000,
    "max_upload_bytes": 512 * 1024 * 1024,
    "max_decompile_classes": 50_000,
    "class_display_limit": 300,
    "dex_class_cap": 0,  # 0 = unlimited
    "dex_lightweight": False,
}

TIER_LIMITS: dict[str, dict[str, Any]] = {
    "low": {
        "tier": "low",
        "max_entry_size": 96 * 1024 * 1024,
        "max_total_size": 384 * 1024 * 1024,
        "max_entries": 35_000,
        "max_upload_bytes": 128 * 1024 * 1024,
        "max_decompile_classes": 600,
        "class_display_limit": 150,
        "dex_class_cap": 12_000,
        "dex_lightweight": True,
    },
    "medium": {
        "tier": "medium",
        "max_entry_size": 128 * 1024 * 1024,
        "max_total_size": 512 * 1024 * 1024,
        "max_entries": 60_000,
        "max_upload_bytes": 192 * 1024 * 1024,
        "max_decompile_classes": 1_200,
        "class_display_limit": 200,
        "dex_class_cap": 20_000,
        "dex_lightweight": True,
    },
    "high": {
        "tier": "high",
        "max_entry_size": 256 * 1024 * 1024,
        "max_total_size": 1 * 1024 * 1024 * 1024,
        "max_entries": 120_000,
        "max_upload_bytes": 320 * 1024 * 1024,
        "max_decompile_classes": 4_000,
        "class_display_limit": 300,
        "dex_class_cap": 50_000,
        "dex_lightweight": True,
    },
}

_ACTIVE: dict[str, Any] = dict(DESKTOP_LIMITS)


def _env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def detect_tier(ram_mb: int = 0, cpu_cores: int = 0) -> str:
    """Pick a performance tier from device RAM and CPU core count."""
    ram = ram_mb or _env_int("APEX_DEVICE_RAM_MB")
    cores = cpu_cores or _env_int("APEX_DEVICE_CPU_CORES")
    if ram <= 0:
        # Chaquopy / Linux on Android often reports Linux; use a safe default.
        if platform.system() == "Linux" and "ANDROID_ROOT" in os.environ:
            ram = 4096
        else:
            return "desktop"
    if ram >= 10_000 or (ram >= 8_000 and cores >= 8):
        return "high"
    if ram >= 3_800 or cores >= 4:
        return "medium"
    return "low"


def configure_device_profile(
    *,
    ram_mb: int = 0,
    cpu_cores: int = 0,
    engine_mode: str = "on_device",
) -> dict[str, Any]:
    """Activate limits for the current runtime and patch analysis constants."""
    global _ACTIVE
    if engine_mode in {"desktop", "remote_server"}:
        profile = dict(DESKTOP_LIMITS)
        profile["engine_mode"] = engine_mode
    else:
        tier = detect_tier(ram_mb, cpu_cores)
        profile = dict(TIER_LIMITS[tier])
        profile["engine_mode"] = "on_device"
        profile["ram_mb"] = ram_mb or _env_int("APEX_DEVICE_RAM_MB")
        profile["cpu_cores"] = cpu_cores or _env_int("APEX_DEVICE_CPU_CORES")

    _ACTIVE = profile
    _patch_analysis_limits(profile)
    return profile


def limits() -> dict[str, Any]:
    return dict(_ACTIVE)


def doctor_fields() -> dict[str, Any]:
    profile = limits()
    return {
        "engine_mode": profile.get("engine_mode", "desktop"),
        "device_tier": profile.get("tier", "desktop"),
        "performance_note": performance_note(),
        "class_display_limit": profile.get("class_display_limit", 300),
        "max_upload_mb": profile.get("max_upload_bytes", DESKTOP_LIMITS["max_upload_bytes"]) // (
            1024 * 1024
        ),
        "max_decompile_classes": profile.get("max_decompile_classes"),
        "dex_class_cap": profile.get("dex_class_cap", 0),
        "ram_mb": profile.get("ram_mb"),
        "cpu_cores": profile.get("cpu_cores"),
    }


def performance_note() -> str:
    mode = _ACTIVE.get("engine_mode", "desktop")
    if mode == "on_device":
        tier = _ACTIVE.get("tier", "low")
        return (
            f"On-device engine ({tier} tier). Use Settings → Desktop computer "
            "to offload analysis to your PC when you need more speed."
        )
    if mode == "remote_server":
        return "Remote mode: analysis runs on the connected desktop/server."
    return "Desktop engine: full limits."


def _patch_analysis_limits(profile: dict[str, Any]) -> None:
    try:
        from apex import analysis as analysis_mod
    except ImportError:
        return
    analysis_mod.MAX_ENTRY_SIZE = int(profile.get("max_entry_size", analysis_mod.MAX_ENTRY_SIZE))
    analysis_mod.MAX_TOTAL_SIZE = int(profile.get("max_total_size", analysis_mod.MAX_TOTAL_SIZE))
    analysis_mod.MAX_ENTRIES = int(profile.get("max_entries", analysis_mod.MAX_ENTRIES))
