"""apksigner verification and signing provider."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from apex.analysis import ApexError

from .registry import get_apksigner_command
from .runner import run_tool
from .types import ProvenanceCollector, timed_operation


def verify_signatures_apksigner(
    apk_path: Path,
    *,
    collector: ProvenanceCollector | None = None,
) -> dict[str, Any]:
    command = get_apksigner_command()
    if not command:
        raise ApexError("apksigner not found; install Android build-tools or set APEX_APKSIGNER")
    collector = collector or ProvenanceCollector()
    with timed_operation(collector, "verify.signatures", "apksigner", None) as op:
        result = run_tool(
            [*command, "verify", "--verbose", "--print-certs", str(apk_path)],
            timeout=120,
        )
        text = result.stdout + result.stderr
        if result.returncode:
            op.status = "error"
            op.reason = text[-500:]
        normalized = parse_apksigner_output(text)
        normalized["provider"] = "apksigner"
        normalized["valid"] = result.returncode == 0
        normalized["raw_excerpt"] = text[-4000:]
        return normalized


def parse_apksigner_output(text: str) -> dict[str, Any]:
    schemes = {"v1": False, "v2": False, "v3": False, "v4": False}
    for key in schemes:
        if re.search(rf"\b{key}\b.*verified", text, re.IGNORECASE):
            schemes[key] = True
        if re.search(rf"Verified using {key}", text, re.IGNORECASE):
            schemes[key] = True
    signers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if current is not None:
            sha256 = re.search(r"SHA-256 digest:\s*([0-9a-f:]+)", line, re.IGNORECASE)
            if sha256:
                current["sha256"] = sha256.group(1)
            sha1 = re.search(r"SHA-1 digest:\s*([0-9a-f:]+)", line, re.IGNORECASE)
            if sha1:
                current["sha1"] = sha1.group(1)
        if "certificate DN:" in line and line.strip().startswith("Signer #"):
            if current:
                signers.append(current)
            current = {"index": int(re.search(r"#(\d+)", line).group(1)), "subject": line.split("certificate DN:", 1)[1].strip()}
    if current:
        signers.append(current)
    warnings = [
        line.strip()
        for line in text.splitlines()
        if "warning" in line.lower() or "does not match" in line.lower()
    ]
    return {
        "status": "valid" if schemes.get("v1") or schemes.get("v2") or schemes.get("v3") else "unknown",
        "schemes": schemes,
        "signers": signers,
        "warnings": warnings,
        "signed": bool(signers) or any(schemes.values()),
    }


def verify_signatures_androguard(apk_path: Path) -> dict[str, Any]:
    try:
        from androguard.core.apk import APK

        parsed = APK(str(apk_path))
        return {
            "provider": "androguard",
            "valid": bool(parsed.is_signed()),
            "signed": bool(parsed.is_signed()),
            "schemes": {
                "v1": bool(parsed.is_signed_v1()),
                "v2": bool(parsed.is_signed_v2()),
                "v3": bool(parsed.is_signed_v3()),
                "v4": False,
            },
            "signers": [],
            "warnings": ["Androguard summary only; install apksigner for certificate fingerprints"],
            "certificate_count": len(parsed.get_certificates()),
        }
    except Exception as exc:
        return {
            "provider": "androguard",
            "valid": False,
            "signed": False,
            "schemes": {"v1": False, "v2": False, "v3": False, "v4": False},
            "signers": [],
            "warnings": [str(exc)],
            "error": str(exc),
        }
