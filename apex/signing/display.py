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
        "subject": primary.get("subject"),
        "warnings": signatures.get("warnings", []),
        "unsupported": [
            field
            for field in ("validity", "lineage", "rotation")
            if field not in signatures
        ],
    }
