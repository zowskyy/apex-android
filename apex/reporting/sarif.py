"""SARIF 2.1.0 output for APEX security findings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.security.rules import rule_metadata
from apex.version import __version__

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
    "review": "warning",
    "warn": "warning",
}

RULE_METADATA: dict[str, dict[str, str]] = {
    "path-traversal": {
        "name": "UnsafeArchivePath",
        "description": "Archive entry resolves outside the extraction root.",
        "cwe": "CWE-22",
    },
    "zip-bomb": {
        "name": "ArchiveExpansionLimit",
        "description": "Archive expansion exceeds configured safety limits.",
        "cwe": "CWE-409",
    },
    "manifest": {
        "name": "ManifestSecurityFlag",
        "description": "Manifest declares a security-relevant configuration.",
        "cwe": "CWE-16",
    },
    "resources": {
        "name": "SensitiveResourceString",
        "description": "Resource table contains a potentially sensitive string.",
        "cwe": "CWE-540",
    },
    "archive": {
        "name": "ArchiveIntegrity",
        "description": "Archive could not be read or validated.",
        "cwe": "CWE-1104",
    },
    "preflight": {
        "name": "PackagingHeuristic",
        "description": "Packaging shape suggests protection or packing.",
        "cwe": "CWE-656",
    },
}


def _rule_for(category: str) -> dict[str, Any]:
    meta = dict(RULE_METADATA.get(category, {}))
    shared = rule_metadata(category)
    meta.setdefault("name", shared["name"])
    meta.setdefault("description", shared["description"])
    meta.setdefault("cwe", shared["cwe"])
    masvs = shared.get("masvs", "MASVS-CODE-1")
    return {
        "id": f"apex/{category}",
        "name": meta["name"],
        "shortDescription": {"text": meta["description"]},
        "fullDescription": {
            "text": (
                f"{meta['description']} APEX reports evidence for human review; "
                "findings are not a malware verdict."
            )
        },
        "properties": {
            "tags": ["security", "mobile", meta["cwe"], masvs],
            "cwe": meta["cwe"],
            "masvs": masvs,
        },
        "defaultConfiguration": {"level": "warning"},
    }


def security_scan_to_sarif(scan: dict[str, Any]) -> dict[str, Any]:
    """Convert an APEX security-scan result into a SARIF 2.1.0 document."""
    findings = scan.get("findings", [])
    categories = sorted({item.get("category", "unknown") for item in findings})
    rules = [_rule_for(category) for category in categories]
    artifact_uri = Path(scan.get("apk", "unknown.apk")).as_uri() if scan.get("apk") else None

    results: list[dict[str, Any]] = []
    for finding in findings:
        category = finding.get("category", "unknown")
        severity = str(finding.get("severity", "medium")).lower()
        result: dict[str, Any] = {
            "ruleId": f"apex/{category}",
            "level": SEVERITY_TO_LEVEL.get(severity, "warning"),
            "message": {"text": finding.get("message", "APEX finding")},
            "properties": {
                "apexSeverity": severity,
                "evidence": finding.get("evidence", ""),
                "cwe": finding.get("cwe", rule_metadata(category)["cwe"]),
                "masvs": finding.get("masvs", rule_metadata(category)["masvs"]),
                "verdictDisclaimer": scan.get("disclaimer", ""),
            },
        }
        if artifact_uri:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": artifact_uri},
                        "region": {"startLine": 1},
                    }
                }
            ]
        results.append(result)

    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "APEX",
                        "informationUri": "https://github.com/zowskyy/apex-android",
                        "version": __version__,
                        "rules": rules,
                    }
                },
                "properties": {
                    "apkSha256": scan.get("sha256"),
                    "verdict": scan.get("verdict"),
                    "findingCount": scan.get("finding_count", len(findings)),
                },
                "results": results,
            }
        ],
    }
