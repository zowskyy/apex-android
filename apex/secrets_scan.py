"""Heuristic secret/credential pattern scan for APK text assets and DEX string pools."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

MAX_SCAN_BYTES = 512 * 1024
MAX_DEX_STRINGS = 50_000
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

SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
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


def scan_text_for_secrets(
    text: str,
    *,
    source: str,
    max_findings: int = 25,
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run secret patterns against a text blob with explicit source attribution."""
    findings = list(existing or [])
    for category, pattern, severity in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                {
                    "severity": severity,
                    "category": f"secret-{category}",
                    "evidence": source,
                    "message": f"possible secret/credential pattern ({source})",
                    "source": source,
                }
            )
            if len(findings) >= max_findings:
                return findings
    return findings


def dex_string_pool(raw: bytes, dex_name: str) -> list[str]:
    """Extract DEX string pool via lightweight Androguard parse."""
    try:
        from apex.analysis import load_dex

        dex, _ = load_dex(raw, lightweight=True)
        return [str(value) for value in dex.get_strings()[:MAX_DEX_STRINGS]]
    except Exception:
        return []


def scan_dex_secrets(
    dex_raw: bytes,
    dex_name: str,
    *,
    max_findings: int = 25,
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """SECRETS-2: scan compiled string literals in the DEX constant pool."""
    findings = list(existing or [])
    source_prefix = f"dex-string-pool:{dex_name}"
    for string_value in dex_string_pool(dex_raw, dex_name):
        findings = scan_text_for_secrets(
            string_value,
            source=source_prefix,
            max_findings=max_findings,
            existing=findings,
        )
        if len(findings) >= max_findings:
            break
    return findings


def scan_apk_secrets(apk_path: Path, max_findings: int = 25) -> list[dict[str, Any]]:
    """Scan text assets and every classes*.dex string pool in an APK."""
    apk_path = Path(apk_path)
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path) as archive:
        dex_names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name.replace("\\", "/"))
        )
        for dex_name in dex_names:
            try:
                findings = scan_dex_secrets(
                    archive.read(dex_name),
                    dex_name,
                    max_findings=max_findings,
                    existing=findings,
                )
            except Exception:
                continue
            if len(findings) >= max_findings:
                return findings

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
            findings = scan_text_for_secrets(
                text,
                source=f"resource-file:{name}",
                max_findings=max_findings,
                existing=findings,
            )
            if len(findings) >= max_findings:
                return findings
    return findings
