"""Heuristic secret/credential pattern scan for APK text assets."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

MAX_SCAN_BYTES = 512 * 1024
TEXT_SUFFIXES = (
    ".xml",
    ".json",
    ".properties",
    ".txt",
    ".js",
    ".html",
    ".env",
    ".cfg",
    ".conf",
    ".kotlin",
    ".java",
    ".gradle",
    ".yaml",
    ".yml",
)

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}"), "critical"),
    (
        "aws-secret-like",
        re.compile(
            r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{16,}"
        ),
        "high",
    ),
    (
        "generic-api-key",
        re.compile(r"(?i)(api[_\-]?key|apikey|secret[_\-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
        "high",
    ),
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "critical",
    ),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "high"),
    ("slack-token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "high"),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "high"),
]


def scan_apk_secrets(apk_path: Path, max_findings: int = 25) -> list[dict[str, Any]]:
    """Scan readable APK entries for common credential patterns."""
    apk_path = Path(apk_path)
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            low = name.lower()
            if info.file_size > MAX_SCAN_BYTES:
                continue
            if not any(low.endswith(suffix) for suffix in TEXT_SUFFIXES):
                continue
            try:
                data = archive.read(name)
            except Exception:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = data.decode("latin-1")
                except Exception:
                    continue
            for category, pattern, severity in _PATTERNS:
                if pattern.search(text):
                    findings.append(
                        {
                            "severity": severity,
                            "category": f"secret-{category}",
                            "evidence": name,
                            "message": f"possible secret/credential pattern in {name}",
                        }
                    )
                    if len(findings) >= max_findings:
                        return findings
    return findings
