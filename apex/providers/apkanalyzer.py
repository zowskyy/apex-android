"""Android SDK apkanalyzer benchmark adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.analysis import ApexError

from .registry import get_apkanalyzer_command
from .runner import run_tool


def benchmark_apk(apk_path: Path) -> dict[str, Any]:
    command = get_apkanalyzer_command()
    if not command:
        return {"status": "unavailable", "provider": "apkanalyzer", "reason": "not installed"}
    apk_path = Path(apk_path)
    sections: dict[str, Any] = {}
    for subject, verb in (
        ("apk", "summary"),
        ("manifest", "permissions"),
        ("dex", "list"),
    ):
        result = run_tool([*command, subject, verb, str(apk_path)], timeout=120)
        sections[f"{subject}.{verb}"] = {
            "returncode": result.returncode,
            "output": (result.stdout + result.stderr)[-8000:],
        }
    return {
        "status": "ok" if all(item["returncode"] == 0 for item in sections.values()) else "error",
        "provider": "apkanalyzer",
        "sections": sections,
    }


def compare_apks(left: Path, right: Path) -> dict[str, Any]:
    command = get_apkanalyzer_command()
    if not command:
        raise ApexError("apkanalyzer not installed")
    result = run_tool(
        [*command, "apk", "compare", "--different-only", str(left), str(right)],
        timeout=180,
    )
    return {
        "provider": "apkanalyzer",
        "returncode": result.returncode,
        "output": (result.stdout + result.stderr)[-12000:],
    }
