"""Native APK certificate and signature-scheme analysis.

Certificate fingerprints, subjects, validity, and signing schemes are core APEX
capabilities and never require an external tool.  ``apksigner`` is used, when
present, only as an independent cross-check of these results.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _format_fingerprint(digest: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in digest)


def _name_to_text(name: Any) -> str | None:
    try:
        return name.human_friendly
    except Exception:
        try:
            return str(name.native)
        except Exception:
            return None


def _certificate_entry(index: int, certificate: Any, der: bytes | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"index": index}
    payload = der
    if payload is None:
        try:
            payload = certificate.dump()
        except Exception:
            payload = None
    if payload:
        entry["sha256"] = _format_fingerprint(hashlib.sha256(payload).digest())
        entry["sha1"] = _format_fingerprint(hashlib.sha1(payload).digest())
        entry["md5"] = _format_fingerprint(hashlib.md5(payload).digest())
    try:
        entry["subject"] = _name_to_text(certificate.subject)
        entry["issuer"] = _name_to_text(certificate.issuer)
        entry["serial_number"] = str(certificate.serial_number)
        entry["not_valid_before"] = certificate["tbs_certificate"]["validity"][
            "not_before"
        ].native.isoformat()
        entry["not_valid_after"] = certificate["tbs_certificate"]["validity"][
            "not_after"
        ].native.isoformat()
        entry["self_signed"] = certificate.self_signed not in (None, "no")
    except Exception as exc:  # certificate fields are best-effort, never fatal
        entry.setdefault("parse_warnings", []).append(str(exc))
    return entry


def analyze_signatures(apk_path: Path) -> dict[str, Any]:
    """Return normalized signing information computed by APEX itself."""
    apk_path = Path(apk_path)
    result: dict[str, Any] = {
        "provider": "apex-native",
        "signed": False,
        "valid": False,
        "schemes": {"v1": False, "v2": False, "v3": False, "v31": False, "v4": False},
        "signers": [],
        "warnings": [],
        "unsupported": [],
    }
    try:
        from androguard.core.apk import APK
    except ImportError:
        result["warnings"].append("androguard is required for signature parsing")
        return result

    try:
        parsed = APK(str(apk_path))
    except Exception as exc:
        result["warnings"].append(f"could not parse APK for signatures: {exc}")
        return result

    schemes = result["schemes"]
    for name, probe in (
        ("v1", "is_signed_v1"),
        ("v2", "is_signed_v2"),
        ("v3", "is_signed_v3"),
        ("v31", "is_signed_v31"),
    ):
        method = getattr(parsed, probe, None)
        if callable(method):
            try:
                schemes[name] = bool(method())
            except Exception:
                schemes[name] = False

    idsig = apk_path.with_name(apk_path.name + ".idsig")
    schemes["v4"] = idsig.is_file()
    if not schemes["v4"]:
        result["unsupported"].append(
            "v4 signature state requires an accompanying .idsig file"
        )

    certificates: list[Any] = []
    try:
        certificates = list(parsed.get_certificates() or [])
    except Exception as exc:
        result["warnings"].append(f"certificate extraction failed: {exc}")

    der_blobs: list[bytes] = []
    for getter in ("get_certificates_der_v3", "get_certificates_der_v2"):
        method = getattr(parsed, getter, None)
        if callable(method):
            try:
                der_blobs.extend(method() or [])
            except Exception:
                pass
    try:
        v1_der = parsed.get_certificates_der_v1()
    except Exception:
        v1_der = []
    der_blobs.extend(v1_der or [])

    signers: list[dict[str, Any]] = []
    for index, certificate in enumerate(certificates, start=1):
        der = der_blobs[index - 1] if index - 1 < len(der_blobs) else None
        signers.append(_certificate_entry(index, certificate, der))
    if not signers and der_blobs:
        for index, der in enumerate(der_blobs, start=1):
            signers.append(
                {
                    "index": index,
                    "sha256": _format_fingerprint(hashlib.sha256(der).digest()),
                    "sha1": _format_fingerprint(hashlib.sha1(der).digest()),
                }
            )

    result["signers"] = signers
    result["signed"] = bool(signers) or any(schemes.values())
    result["valid"] = result["signed"]
    result["certificate_count"] = len(signers)

    if len(signers) > 1:
        result["rotation"] = {
            "state": "multiple_signers_present",
            "detail": "Multiple signing certificates found; review lineage before trusting",
        }
    else:
        result["unsupported"].append(
            "certificate rotation lineage is only reported when multiple signers are present"
        )

    if result["signed"] and not any(schemes.values()):
        result["warnings"].append(
            "certificates were found but no signature scheme could be confirmed"
        )
    if not result["signed"]:
        result["warnings"].append("no signing certificates found in this APK")

    result["trust_note"] = (
        "A valid signature proves integrity relative to its signer. "
        "It does not establish publisher identity or trustworthiness."
    )
    return result


def cross_check_with_apksigner(
    apk_path: Path,
    native: dict[str, Any],
) -> dict[str, Any]:
    """Compare native results against apksigner when that tool is installed."""
    from apex.analysis import ApexError
    from apex.providers.apksigner import verify_signatures_apksigner

    try:
        official = verify_signatures_apksigner(apk_path)
    except ApexError as exc:
        return {"status": "unavailable", "reason": str(exc)}

    native_prints = {
        item.get("sha256") for item in native.get("signers", []) if item.get("sha256")
    }
    official_prints = {
        item.get("sha256") for item in official.get("signers", []) if item.get("sha256")
    }
    differences: list[str] = []
    if official_prints and native_prints != official_prints:
        differences.append("certificate SHA-256 fingerprints differ")
    for scheme in ("v1", "v2", "v3"):
        if scheme in official.get("schemes", {}) and native["schemes"].get(scheme) != official[
            "schemes"
        ].get(scheme):
            differences.append(f"{scheme} scheme state differs")
    return {
        "status": "match" if not differences else "mismatch",
        "differences": differences,
        "apksigner_signers": official.get("signers", []),
        "apksigner_schemes": official.get("schemes", {}),
    }
