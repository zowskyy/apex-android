"""Platform wrapper discovery for APEX."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def wrapper_matrix() -> dict[str, dict[str, str]]:
    root = REPO_ROOT
    return {
        "windows_gui": {
            "platform": "Windows",
            "use": "Local web UI",
            "path": str(root / "wrappers/windows/apex-gui.bat"),
        },
        "windows_mobile": {
            "platform": "Windows",
            "use": "Phone browser mode (LAN)",
            "path": str(root / "wrappers/windows/apex-mobile.bat"),
        },
        "windows_powershell": {
            "platform": "Windows",
            "use": "PowerShell launcher",
            "path": str(root / "wrappers/windows/apex.ps1"),
        },
        "macos_gui": {
            "platform": "macOS",
            "use": "Local web UI (.command)",
            "path": str(root / "wrappers/macos/apex-gui.command"),
        },
        "macos_mobile": {
            "platform": "macOS",
            "use": "Phone browser mode (.command)",
            "path": str(root / "wrappers/macos/apex-mobile.command"),
        },
        "macos_app_gui": {
            "platform": "macOS",
            "use": "Local web UI (.app after create-apps.sh)",
            "path": str(root / "wrappers/macos/dist/APEX.app"),
        },
        "macos_app_mobile": {
            "platform": "macOS",
            "use": "Phone mode (.app after create-apps.sh)",
            "path": str(root / "wrappers/macos/dist/APEX Mobile.app"),
        },
        "linux_gui": {
            "platform": "Linux",
            "use": "Local web UI",
            "path": str(root / "wrappers/linux/apex-gui.sh"),
        },
        "linux_mobile": {
            "platform": "Linux",
            "use": "Phone browser mode",
            "path": str(root / "wrappers/linux/apex-mobile.sh"),
        },
        "android_client_apk": {
            "platform": "Android",
            "use": "WebView shell (build with wrappers/android/build.sh)",
            "path": str(root / "wrappers/android/dist/apex-client.apk"),
        },
        "ios_guide": {
            "platform": "iOS",
            "use": "Safari + Add to Home Screen",
            "path": str(root / "wrappers/ios/README.md"),
        },
        "docker_compose": {
            "platform": "Docker",
            "use": "Containerized mobile server",
            "path": str(root / "wrappers/docker/docker-compose.yml"),
        },
    }


def recommended_wrappers() -> list[str]:
    system = platform.system()
    if system == "Windows":
        return ["windows_gui", "windows_mobile", "windows_powershell"]
    if system == "Darwin":
        return ["macos_gui", "macos_mobile", "macos_app_gui", "macos_app_mobile"]
    if system == "Linux":
        return ["linux_gui", "linux_mobile", "docker_compose"]
    return ["docker_compose"]


def run_install() -> int:
    root = REPO_ROOT
    if platform.system() == "Windows":
        script = root / "wrappers/install.ps1"
        if not script.is_file():
            raise FileNotFoundError(script)
        completed = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=root,
            check=False,
        )
        return completed.returncode
    script = root / "wrappers/install.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    completed = subprocess.run(["bash", str(script)], cwd=root, check=False)
    return completed.returncode
