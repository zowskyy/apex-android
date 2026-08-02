"""Signing presentation helpers."""

from __future__ import annotations

from typing import Any


def format_signing_panel(signatures: dict[str, Any]) -> dict[str, Any]:
    signers = signatures.get("signers") or []
    primary = signers[0] if signers else {}
    return {
        "provider": signatures.get("provider"),
        "valid": signatures.get("valid", signatures.get("signed", False)),
        "signed": signatures.get("signed", False),
        "schemes": signatures.get("schemes", {}),
        "fingerprint_sha256": primary.get("sha256"),
        "fingerprint_sha1": primary.get("sha1"),
        "fingerprint_md5": primary.get("md5"),
        "subject": primary.get("subject"),
        "issuer": primary.get("issuer"),
        "serial_number": primary.get("serial_number"),
        "not_valid_before": primary.get("not_valid_before"),
        "not_valid_after": primary.get("not_valid_after"),
        "self_signed": primary.get("self_signed"),
        "signer_count": len(signers),
        "signers": signers,
        "rotation": signatures.get("rotation"),
        "cross_check": signatures.get("cross_check", {"status": "not_run"}),
        "warnings": signatures.get("warnings", []),
        "unsupported": signatures.get("unsupported", []),
        "trust_note": signatures.get("trust_note"),
    }
