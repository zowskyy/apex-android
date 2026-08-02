"""Canonical APEX security rule catalog with CWE and OWASP MASVS mapping.

Each finding category maps to a stable rule id, a human name, a CWE reference,
and an OWASP MASVS control. This catalog is shared by the security scanner and
the SARIF exporter so both stay consistent.
"""

from __future__ import annotations

from typing import Any

RULES: dict[str, dict[str, str]] = {
    "path-traversal": {
        "name": "UnsafeArchivePath",
        "description": "Archive entry resolves outside the extraction root.",
        "cwe": "CWE-22",
        "masvs": "MASVS-STORAGE-2",
    },
    "zip-bomb": {
        "name": "ArchiveExpansionLimit",
        "description": "Archive expansion exceeds configured safety limits.",
        "cwe": "CWE-409",
        "masvs": "MASVS-RESILIENCE-3",
    },
    "resource-path-traversal": {
        "name": "SensitiveResourceString",
        "description": "Resource table contains a string with an unsafe path.",
        "cwe": "CWE-22",
        "masvs": "MASVS-STORAGE-2",
    },
    "manifest": {
        "name": "ManifestSecurityFlag",
        "description": "Manifest declares a security-relevant configuration.",
        "cwe": "CWE-16",
        "masvs": "MASVS-PLATFORM-1",
    },
    "resources": {
        "name": "SensitiveResourceString",
        "description": "Resource table contains a potentially sensitive string.",
        "cwe": "CWE-540",
        "masvs": "MASVS-STORAGE-1",
    },
    "archive": {
        "name": "ArchiveIntegrity",
        "description": "Archive could not be read or validated.",
        "cwe": "CWE-1104",
        "masvs": "MASVS-RESILIENCE-3",
    },
    "preflight": {
        "name": "PackagingHeuristic",
        "description": "Packaging shape suggests protection or packing.",
        "cwe": "CWE-656",
        "masvs": "MASVS-RESILIENCE-1",
    },
    "exported-component": {
        "name": "ExportedComponent",
        "description": "Component is exported without a guarding permission.",
        "cwe": "CWE-926",
        "masvs": "MASVS-PLATFORM-1",
    },
    "cleartext-traffic": {
        "name": "CleartextTraffic",
        "description": "App permits cleartext (unencrypted) network traffic.",
        "cwe": "CWE-319",
        "masvs": "MASVS-NETWORK-1",
    },
    "network-security-config": {
        "name": "NetworkSecurityConfig",
        "description": "Network security configuration weakens transport security.",
        "cwe": "CWE-319",
        "masvs": "MASVS-NETWORK-2",
    },
    "secret-material": {
        "name": "HardcodedSecret",
        "description": "Embedded credential or key material was detected.",
        "cwe": "CWE-798",
        "masvs": "MASVS-CRYPTO-1",
    },
    "insecure-crypto": {
        "name": "InsecureCryptography",
        "description": "Weak or broken cryptographic primitive referenced.",
        "cwe": "CWE-327",
        "masvs": "MASVS-CRYPTO-1",
    },
    "webview": {
        "name": "WebViewMisconfiguration",
        "description": "WebView configuration may expose native code or content.",
        "cwe": "CWE-749",
        "masvs": "MASVS-PLATFORM-2",
    },
    "ios-transport-security": {
        "name": "AppTransportSecurity",
        "description": "iOS App Transport Security allows insecure connections.",
        "cwe": "CWE-319",
        "masvs": "MASVS-NETWORK-1",
    },
    "ios-binary-protection": {
        "name": "BinaryHardening",
        "description": "Mach-O binary is missing a recommended hardening feature.",
        "cwe": "CWE-1277",
        "masvs": "MASVS-RESILIENCE-1",
    },
}


def rule_metadata(category: str) -> dict[str, str]:
    """Return metadata for a category, with a sensible default when unknown."""
    return RULES.get(
        category,
        {
            "name": category.replace("-", " ").title().replace(" ", ""),
            "description": f"APEX static finding in category {category}.",
            "cwe": "CWE-noinfo",
            "masvs": "MASVS-CODE-1",
        },
    )


def annotate(finding: dict[str, Any]) -> dict[str, Any]:
    """Attach cwe/masvs metadata to a finding in place and return it."""
    meta = rule_metadata(str(finding.get("category", "unknown")))
    finding.setdefault("cwe", meta["cwe"])
    finding.setdefault("masvs", meta["masvs"])
    return finding
