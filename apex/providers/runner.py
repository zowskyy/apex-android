"""Bounded subprocess execution and external-tool resolution."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from apex.analysis import ApexError

SECRET_PATTERNS = (
    re.compile(r"pass:[^\s]+", re.IGNORECASE),
    re.compile(r"--ks-pass\s+\S+", re.IGNORECASE),
    re.compile(r"--key-pass\s+\S+", re.IGNORECASE),
)

TOOL_ENV: dict[str, str] = {
    "jadx": "APEX_JADX",
    "apktool": "APEX_APKTOOL",
    "apktool_jar": "APEX_APKTOOL_JAR",
    "apksigner": "APEX_APKSIGNER",
    "apkanalyzer": "APEX_APKANALYZER",
    "bundletool": "APEX_BUNDLETOOL_JAR",
    "adb": "APEX_ADB",
    "aapt2": "APEX_AAPT2",
    "java": "APEX_JAVA",
}

INSTALL_HINTS: dict[str, str] = {
    "jadx": "Install jadx or set APEX_JADX to the jadx executable",
    "apktool": "Install apktool or set APEX_APKTOOL_JAR to apktool.jar",
    "apksigner": "Install Android build-tools apksigner or set APEX_APKSIGNER",
    "apkanalyzer": "Install Android SDK cmdline-tools and apkanalyzer, or set APEX_APKANALYZER",
    "bundletool": "Download bundletool.jar and set APEX_BUNDLETOOL_JAR",
    "adb": "Install Android platform-tools adb or set APEX_ADB",
    "aapt2": "Install Android build-tools aapt2 or set APEX_AAPT2",
    "java": "Install a Java runtime or set APEX_JAVA",
}


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


def redact_command(argv: Sequence[str]) -> list[str]:
    rendered = " ".join(argv)
    for pattern in SECRET_PATTERNS:
        rendered = pattern.sub("<redacted>", rendered)
    return rendered.split(" ")


def resolve_executable(name: str, *, env_key: str | None = None) -> tuple[str | None, str]:
    env_key = env_key or TOOL_ENV.get(name, f"APEX_{name.upper()}")
    override = os.environ.get(env_key or "")
    if override and Path(override).exists():
        return override, "env"
    managed = Path.home() / ".apex" / "tools" / name
    if managed.is_file():
        return str(managed), "managed"
    found = shutil.which(name)
    if found:
        return found, "path"
    return None, "missing"


def resolve_java_command() -> list[str] | None:
    java, _ = resolve_executable("java", env_key=TOOL_ENV["java"])
    if not java:
        return None
    return [java]


def resolve_jar_command(jar_env: str, jar_name: str) -> list[str] | None:
    jar = os.environ.get(jar_env)
    if jar and Path(jar).is_file():
        java = resolve_java_command()
        if java:
            return [*java, "-jar", jar]
    return None


def resolve_apktool_command() -> list[str] | None:
    executable, _ = resolve_executable("apktool", env_key=TOOL_ENV["apktool"])
    if executable:
        return [executable]
    return resolve_jar_command(TOOL_ENV["apktool_jar"], "apktool.jar")


def probe_version(argv: list[str], *, pattern: str = r"(\d+\.\d+(?:\.\d+)?)") -> str | None:
    if not argv:
        return None
    try:
        result = run_tool([*argv[:1], "--version"], timeout=15)
    except ApexError:
        try:
            result = run_tool(argv[:1] + ["--version"], timeout=15)
        except ApexError:
            return None
    text = (result.stdout + result.stderr).strip()
    match = re.search(pattern, text)
    return match.group(1) if match else text.splitlines()[0][:80] if text else None


def run_tool(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> CommandResult:
    if not argv:
        raise ApexError("empty command")
    import time

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env={**os.environ, **(env or {})},
        )
    except subprocess.TimeoutExpired as exc:
        raise ApexError(f"command timed out after {timeout}s: {redact_command(argv)}") from exc
    except FileNotFoundError as exc:
        raise ApexError(f"executable not found: {argv[0]}") from exc
    duration_ms = int((time.perf_counter() - start) * 1000)
    stdout = (completed.stdout or "")[-500_000:]
    stderr = (completed.stderr or "")[-500_000:]
    return CommandResult(argv, completed.returncode, stdout, stderr, duration_ms)
