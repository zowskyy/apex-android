"""Hard-gate scanners for APK static analysis (Slice 1 subset)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from apex.analysis import ANDROID_NS, _xml_bytes, inspect_apk
from apex.gate.models import GateFinding, GateStatus

# Privacy-sensitive permissions that should use maxSdkVersion when declared.
_SENSITIVE_PERMISSIONS = frozenset(
    {
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_CONTACTS",
        "android.permission.READ_CALL_LOG",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.CAMERA",
        "android.permission.RECORD_AUDIO",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
    }
)


def scan_manifest(apk_path: Path, msv: int) -> list[GateFinding]:
    findings: list[GateFinding] = []
    inspected = inspect_apk(apk_path)
    manifest = inspected.get("manifest") or {}
    if manifest.get("error"):
        findings.append(
            GateFinding(
                scanner="manifest",
                status=GateStatus.FAIL,
                category="manifest-parse",
                message="AndroidManifest could not be parsed",
                evidence=str(manifest.get("error")),
            )
        )
        return findings

    min_sdk_raw = str(manifest.get("min_sdk") or "").strip()
    if not min_sdk_raw:
        findings.append(
            GateFinding(
                scanner="manifest",
                status=GateStatus.WARN,
                category="min-sdk",
                message="minSdkVersion not found in manifest",
            )
        )
    else:
        try:
            min_sdk = int(min_sdk_raw)
            if min_sdk < msv:
                findings.append(
                    GateFinding(
                        scanner="manifest",
                        status=GateStatus.FAIL,
                        category="min-sdk",
                        message=f"minSdkVersion {min_sdk} is below required MSV {msv}",
                        evidence=f"minSdkVersion={min_sdk}",
                    )
                )
            else:
                findings.append(
                    GateFinding(
                        scanner="manifest",
                        status=GateStatus.PASS,
                        category="min-sdk",
                        message=f"minSdkVersion {min_sdk} meets MSV {msv}",
                        evidence=f"minSdkVersion={min_sdk}",
                    )
                )
        except ValueError:
            findings.append(
                GateFinding(
                    scanner="manifest",
                    status=GateStatus.WARN,
                    category="min-sdk",
                    message=f"minSdkVersion is not numeric: {min_sdk_raw}",
                    evidence=min_sdk_raw,
                )
            )

    target_sdk = str(manifest.get("target_sdk") or "").strip()
    if target_sdk:
        try:
            if int(target_sdk) < 28:
                findings.append(
                    GateFinding(
                        scanner="manifest",
                        status=GateStatus.WARN,
                        category="target-sdk",
                        message=f"targetSdkVersion {target_sdk} is below modern baseline 28",
                        evidence=f"targetSdkVersion={target_sdk}",
                    )
                )
        except ValueError:
            pass

    _scan_permission_nodes(apk_path, findings)
    _scan_exported_components(apk_path, findings)

    activities = manifest.get("activities") or []
    if not activities:
        findings.append(
            GateFinding(
                scanner="manifest",
                status=GateStatus.WARN,
                category="entry-points",
                message="No activities declared",
            )
        )
    else:
        findings.append(
            GateFinding(
                scanner="manifest",
                status=GateStatus.PASS,
                category="entry-points",
                message=f"{len(activities)} activity entry point(s)",
                evidence=", ".join(activities[:5]),
            )
        )

    return findings


def _scan_permission_nodes(apk_path: Path, findings: list[GateFinding]) -> None:
    try:
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
                return
            root = ET.fromstring(_xml_bytes(archive.read(manifest_name)))
    except Exception as exc:
        findings.append(
            GateFinding(
                scanner="manifest",
                status=GateStatus.WARN,
                category="permissions",
                message="Could not deep-parse permissions",
                evidence=str(exc),
            )
        )
        return

    for node in root.findall("uses-permission"):
        name = node.attrib.get(f"{ANDROID_NS}name", "")
        if not name:
            continue
        max_sdk = node.attrib.get(f"{ANDROID_NS}maxSdkVersion")
        if name in _SENSITIVE_PERMISSIONS and not max_sdk:
            findings.append(
                GateFinding(
                    scanner="manifest",
                    status=GateStatus.WARN,
                    category="privacy-permission",
                    message=f"{name} declared without android:maxSdkVersion",
                    evidence=name,
                )
            )


def _scan_exported_components(apk_path: Path, findings: list[GateFinding]) -> None:
    try:
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
                return
            root = ET.fromstring(_xml_bytes(archive.read(manifest_name)))
    except Exception:
        return

    application = root.find("application")
    if application is None:
        return

    for tag in ("activity", "service", "receiver", "provider"):
        for node in application.findall(tag):
            exported = node.attrib.get(f"{ANDROID_NS}exported", "")
            if exported.lower() == "true":
                name = node.attrib.get(f"{ANDROID_NS}name", tag)
                findings.append(
                    GateFinding(
                        scanner="manifest",
                        status=GateStatus.WARN,
                        category="exported-component",
                        message=f"Exported {tag} may widen attack surface",
                        evidence=name,
                    )
                )


def scan_dex(apk_path: Path) -> list[GateFinding]:
    findings: list[GateFinding] = []
    inspected = inspect_apk(apk_path)
    dex_files = inspected.get("dex_files") or []
    if not dex_files:
        findings.append(
            GateFinding(
                scanner="dex",
                status=GateStatus.FAIL,
                category="dex-missing",
                message="No classes*.dex files found — not a valid Android application package",
            )
        )
        return findings

    findings.append(
        GateFinding(
            scanner="dex",
            status=GateStatus.PASS,
            category="dex-present",
            message=f"{len(dex_files)} DEX file(s) present",
            evidence=", ".join(dex_files),
        )
    )

    try:
        with zipfile.ZipFile(apk_path) as archive:
            class_total = 0
            for dex_name in dex_files:
                from apex.analysis import dex_metadata

                meta = dex_metadata(archive.read(dex_name), dex_name)
                class_total += len(meta.get("classes") or [])
            if class_total == 0:
                findings.append(
                    GateFinding(
                        scanner="dex",
                        status=GateStatus.WARN,
                        category="dex-empty",
                        message="DEX files present but no classes parsed",
                    )
                )
            else:
                findings.append(
                    GateFinding(
                        scanner="dex",
                        status=GateStatus.PASS,
                        category="dex-classes",
                        message=f"{class_total} DEX classes indexed",
                        evidence=str(class_total),
                    )
                )
    except Exception as exc:
        findings.append(
            GateFinding(
                scanner="dex",
                status=GateStatus.WARN,
                category="dex-parse",
                message="DEX metadata scan failed",
                evidence=str(exc),
            )
        )

    return findings


def scan_security(apk_path: Path) -> list[GateFinding]:
    from apex.workflows import security_scan

    findings: list[GateFinding] = []
    report = security_scan(apk_path)
    raw_findings = report.get("findings") or []
    critical = sum(1 for f in raw_findings if f.get("severity") == "critical")
    high = sum(1 for f in raw_findings if f.get("severity") == "high")

    if critical:
        findings.append(
            GateFinding(
                scanner="security",
                status=GateStatus.FAIL,
                category="security-critical",
                message=f"{critical} critical security finding(s)",
                evidence=str(critical),
            )
        )
    elif high > 5:
        findings.append(
            GateFinding(
                scanner="security",
                status=GateStatus.FAIL,
                category="security-high",
                message=f"{high} high-severity findings (limit 5)",
                evidence=str(high),
            )
        )
    elif high:
        findings.append(
            GateFinding(
                scanner="security",
                status=GateStatus.WARN,
                category="security-high",
                message=f"{high} high-severity finding(s)",
                evidence=str(high),
            )
        )
    else:
        findings.append(
            GateFinding(
                scanner="security",
                status=GateStatus.PASS,
                category="security-verdict",
                message=f"Security verdict: {report.get('verdict', 'CLEAN')}",
                evidence=report.get("verdict", ""),
            )
        )

    for item in raw_findings[:20]:
        severity = str(item.get("severity", "info")).lower()
        status = GateStatus.FAIL if severity == "critical" else GateStatus.WARN
        if severity in {"low", "info"}:
            continue
        findings.append(
            GateFinding(
                scanner="security",
                status=status,
                category=str(item.get("category", "finding")),
                message=str(item.get("message", "")),
                evidence=str(item.get("evidence", "")),
            )
        )

    return findings
