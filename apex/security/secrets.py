"""Embedded secret detection over extracted strings.

Detection is precision-first: high-confidence provider patterns plus an
entropy gate. Every match is redacted before it enters a finding, report, or
provenance record — APEX never emits a recovered secret in its output.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

# (id, severity, compiled pattern). Patterns target well-known credential
# formats to keep false positives low.
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("aws-access-key", "high", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google-api-key", "high", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("firebase-url", "medium", re.compile(r"https://[a-z0-9\-]+\.firebaseio\.com")),
    ("slack-token", "high", re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,48}")),
    ("stripe-secret-key", "critical", re.compile(r"sk_live_[0-9A-Za-z]{24}")),
    ("github-token", "high", re.compile(r"gh[pousr]_[0-9A-Za-z]{36}")),
    ("private-key-block", "critical",
     re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("jwt", "medium",
     re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{6,}")),
    ("twilio-key", "high", re.compile(r"SK[0-9a-fA-F]{32}")),
    ("bearer-token", "low", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{20,}")),
]

_MAX_FINDINGS = 200


def shannon_entropy(value: str) -> float:
    """Return the Shannon entropy (bits per character) of ``value``."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def redact(secret: str) -> str:
    """Mask a secret, preserving only a short prefix for identification."""
    secret = secret.strip()
    if len(secret) <= 8:
        return "•" * len(secret)
    return f"{secret[:4]}{'•' * 8}{secret[-2:]}"


def scan_secrets(strings: Iterable[str], *, source: str = "strings") -> list[dict[str, Any]]:
    """Scan an iterable of strings for embedded secrets.

    Returns a list of redacted findings. The same secret is reported once.
    """
    seen: set[tuple[str, str]] = set()
    findings: list[dict[str, Any]] = []
    for raw in strings:
        if not raw or len(raw) > 8192:
            continue
        for secret_id, severity, pattern in _PATTERNS:
            match = pattern.search(raw)
            if not match:
                continue
            token = match.group(0)
            # Entropy gate for the generic bearer pattern to cut noise.
            if secret_id == "bearer-token" and shannon_entropy(token) < 3.5:
                continue
            redacted = redact(token)
            key = (secret_id, redacted)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "severity": severity,
                    "category": "secret-material",
                    "secret_type": secret_id,
                    "source": source,
                    "evidence": redacted,
                    "entropy": round(shannon_entropy(token), 2),
                    "message": f"possible {secret_id.replace('-', ' ')} embedded in {source}",
                }
            )
            if len(findings) >= _MAX_FINDINGS:
                return findings
    return findings
