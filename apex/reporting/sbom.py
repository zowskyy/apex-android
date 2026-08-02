"""CycloneDX software bill of materials (SBOM) generation.

Produces a CycloneDX 1.5 JSON document from APEX's detected libraries and
trackers. This is a standard, machine-readable supply-chain artifact consumed
by DevSecOps tooling.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

SPEC_VERSION = "1.5"


def _bom_ref(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def build_sbom(app: dict[str, Any], detections: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a CycloneDX 1.5 BOM for the given app and detections.

    ``app`` provides ``name``, ``version``, ``platform`` and optional ``sha256``.
    ``detections`` is the list produced by :func:`apex.intel.detect.detect_components`.
    """
    from apex.version import __version__

    app_name = app.get("name") or "unknown-application"
    app_version = app.get("version") or "0"
    seed = f"{app_name}:{app_version}:{app.get('sha256', '')}".encode("utf-8")
    serial = "urn:uuid:" + hashlib.sha1(seed).hexdigest()[:32]

    components: list[dict[str, Any]] = []
    for det in detections:
        properties = [
            {"name": "apex:platform", "value": det.get("platform", "unknown")},
            {"name": "apex:kind", "value": det.get("kind", "library")},
        ]
        if det.get("kind") == "tracker":
            properties.append({"name": "apex:tracker", "value": "true"})
        for category in det.get("categories", []):
            properties.append({"name": "apex:category", "value": category})
        for evidence in det.get("evidence", []):
            properties.append({"name": "apex:evidence", "value": evidence})
        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": _bom_ref(det.get("kind", "library"), det["id"]),
            "name": det["name"],
            "properties": properties,
        }
        if det.get("website"):
            component["externalReferences"] = [
                {"type": "website", "url": det["website"]}
            ]
        components.append(component)

    metadata_component: dict[str, Any] = {
        "type": "application",
        "bom-ref": app_name,
        "name": app_name,
        "version": str(app_version),
        "properties": [{"name": "apex:platform", "value": app.get("platform", "android")}],
    }
    if app.get("sha256"):
        metadata_component["hashes"] = [{"alg": "SHA-256", "content": app["sha256"]}]

    return {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tools": [{"vendor": "APEX", "name": "apex", "version": __version__}],
            "component": metadata_component,
        },
        "components": components,
    }
