"""Network security config static analysis (blueprint NETSEC-1)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from apex.analysis import ANDROID_NS, _xml_bytes, decode_binary_xml


def _find_netsec_xml(archive: zipfile.ZipFile, resource_ref: str) -> tuple[str, bytes] | None:
    """Resolve @xml/name style manifest reference to zip entry bytes."""
    name = resource_ref.strip()
    if name.startswith("@xml/"):
        stem = name.split("/", 1)[1]
    elif "/" in name:
        stem = Path(name).name
    else:
        stem = name.lstrip("@")
    candidates = [
        f"res/xml/{stem}.xml",
        f"res/xml/{stem}",
    ]
    for entry in archive.namelist():
        normalized = entry.replace("\\", "/")
        if normalized in candidates or normalized.endswith(f"/xml/{stem}.xml"):
            return normalized, archive.read(entry)
    for entry in archive.namelist():
        if stem in entry and "/xml/" in entry.replace("\\", "/"):
            return entry, archive.read(entry)
    return None


def scan_network_security(apk_path: Path) -> list[dict[str, Any]]:
    apk_path = Path(apk_path)
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path) as archive:
        manifest_name = next(
            (
                candidate
                for candidate in ("AndroidManifest.xml", "base/manifest/AndroidManifest.xml")
                if candidate in archive.namelist()
            ),
            "",
        )
        if not manifest_name:
            return findings
        raw_manifest = archive.read(manifest_name)
        try:
            root = ET.fromstring(_xml_bytes(raw_manifest))
        except Exception:
            return findings
        application = root.find("application")
        if application is None:
            return findings
        cleartext = application.attrib.get(f"{ANDROID_NS}usesCleartextTraffic", "")
        if cleartext.lower() == "true":
            findings.append(
                {
                    "severity": "medium",
                    "category": "netsec-cleartext-manifest",
                    "message": "android:usesCleartextTraffic=true on application",
                    "evidence": "manifest",
                }
            )
        nsc_ref = application.attrib.get(f"{ANDROID_NS}networkSecurityConfig", "")
        if not nsc_ref:
            return findings
        resolved = _find_netsec_xml(archive, nsc_ref)
        if not resolved:
            findings.append(
                {
                    "severity": "low",
                    "category": "netsec-config-missing",
                    "message": f"networkSecurityConfig reference not found in APK: {nsc_ref}",
                    "evidence": nsc_ref,
                }
            )
            return findings
        path, raw_xml = resolved
        try:
            xml_text = decode_binary_xml(raw_xml)
            nsc_root = ET.fromstring(xml_text)
        except Exception as exc:
            findings.append(
                {
                    "severity": "low",
                    "category": "netsec-parse-error",
                    "message": f"Could not parse network security config: {exc}",
                    "evidence": path,
                }
            )
            return findings

        for node in nsc_root.iter():
            tag = node.tag.split("}")[-1]
            if tag == "certificates":
                src = node.attrib.get("src", node.attrib.get(f"{ANDROID_NS}src", ""))
                if src == "user":
                    findings.append(
                        {
                            "severity": "high",
                            "category": "netsec-user-ca",
                            "message": "Network config trusts user-installed CA certificates (MITM risk)",
                            "evidence": path,
                        }
                    )
            if tag == "domain-config" or tag == "base-config":
                cleartext_perm = node.attrib.get(
                    "cleartextTrafficPermitted",
                    node.attrib.get(f"{ANDROID_NS}cleartextTrafficPermitted", ""),
                )
                if cleartext_perm.lower() == "true":
                    domains = [
                        child.attrib.get("includeSubdomains", "")
                        for child in node.findall("domain")
                    ]
                    findings.append(
                        {
                            "severity": "medium",
                            "category": "netsec-cleartext-domain",
                            "message": "Network config permits cleartext for domain/base config",
                            "evidence": path + " domains=" + ",".join(d for d in domains if d),
                        }
                    )
    return findings
