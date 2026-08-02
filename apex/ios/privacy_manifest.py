"""Apple privacy manifest (PrivacyInfo.xcprivacy) analysis.

Parses the plist Apple requires for App Store submission and reports declared
tracking, tracking domains, collected data types, and Required Reason API
categories. Used to correlate declared privacy against observed behavior.
"""

from __future__ import annotations

import plistlib
from typing import Any

# Required Reason API category codes -> human labels (Apple developer docs).
_REQUIRED_REASON_APIS = {
    "NSPrivacyAccessedAPICategoryFileTimestamp": "File timestamp APIs",
    "NSPrivacyAccessedAPICategorySystemBootTime": "System boot time APIs",
    "NSPrivacyAccessedAPICategoryDiskSpace": "Disk space APIs",
    "NSPrivacyAccessedAPICategoryActiveKeyboards": "Active keyboard APIs",
    "NSPrivacyAccessedAPICategoryUserDefaults": "User defaults APIs",
}


def parse_privacy_manifest(raw: bytes) -> dict[str, Any]:
    """Parse a PrivacyInfo.xcprivacy plist (binary or XML)."""
    try:
        data = plistlib.loads(raw)
    except Exception as exc:
        return {"valid": False, "error": str(exc)}
    if not isinstance(data, dict):
        return {"valid": False, "error": "privacy manifest is not a dictionary"}

    tracking = bool(data.get("NSPrivacyTracking", False))
    domains = list(data.get("NSPrivacyTrackingDomains", []) or [])
    collected = [
        str(item.get("NSPrivacyCollectedDataType", ""))
        for item in data.get("NSPrivacyCollectedDataTypes", []) or []
        if isinstance(item, dict)
    ]
    accessed = []
    for item in data.get("NSPrivacyAccessedAPITypes", []) or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("NSPrivacyAccessedAPIType", ""))
        accessed.append(
            {
                "category": category,
                "label": _REQUIRED_REASON_APIS.get(category, category),
                "reasons": list(item.get("NSPrivacyAccessedAPITypeReasons", []) or []),
            }
        )
    return {
        "valid": True,
        "tracking": tracking,
        "tracking_domains": domains,
        "collected_data_types": [c for c in collected if c],
        "accessed_api_categories": accessed,
    }


def analyze_privacy_manifest(raw: bytes) -> dict[str, Any]:
    """Parse the manifest and add derived consistency findings."""
    parsed = parse_privacy_manifest(raw)
    if not parsed.get("valid"):
        return parsed
    findings: list[dict[str, Any]] = []
    if parsed["tracking"] and not parsed["tracking_domains"]:
        findings.append(
            {
                "severity": "low",
                "message": "NSPrivacyTracking is true but no tracking domains are declared",
            }
        )
    for accessed in parsed["accessed_api_categories"]:
        if not accessed["reasons"]:
            findings.append(
                {
                    "severity": "medium",
                    "message": (
                        f"Required Reason API '{accessed['label']}' declared without a reason "
                        "code (App Store rejection risk)"
                    ),
                }
            )
    parsed["findings"] = findings
    return parsed
