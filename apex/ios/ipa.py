"""IPA (iOS application archive) inspection.

Opens an ``.ipa`` (a ZIP), locates the ``.app`` bundle, parses ``Info.plist``,
the main Mach-O binary, the privacy manifest, and embedded frameworks, then
runs cross-platform tracker/library detection. All reads are bounded and no
entry is written to disk.
"""

from __future__ import annotations

import plistlib
import posixpath
import zipfile
from pathlib import Path
from typing import Any

from apex.analysis import ApexError, sha256_file
from apex.intel.detect import detect_ios
from apex.ios.macho import parse_macho
from apex.ios.privacy_manifest import analyze_privacy_manifest
from apex.security.rules import annotate

_MAX_BINARY_BYTES = 300 * 1024 * 1024


def _find_app_root(names: list[str]) -> str | None:
    for name in names:
        parts = name.split("/")
        if len(parts) >= 2 and parts[0] == "Payload" and parts[1].endswith(".app"):
            return f"Payload/{parts[1]}/"
    return None


def _read_plist(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        return plistlib.loads(archive.read(name))
    except Exception:
        return {}


def inspect_ipa(ipa_path: Path) -> dict[str, Any]:
    """Return a structured analysis report for an iOS ``.ipa`` file."""
    ipa_path = Path(ipa_path)
    if not ipa_path.is_file():
        raise ApexError(f"IPA not found: {ipa_path}")
    try:
        archive = zipfile.ZipFile(ipa_path)
    except zipfile.BadZipFile as exc:
        raise ApexError(f"invalid IPA/ZIP: {exc}") from exc

    with archive:
        names = archive.namelist()
        app_root = _find_app_root(names)
        if not app_root:
            raise ApexError("IPA does not contain a Payload/*.app bundle")

        info = _read_plist(archive, app_root + "Info.plist")
        executable = str(info.get("CFBundleExecutable", ""))
        binary_summary: dict[str, Any] = {"valid": False}
        if executable:
            binary_name = app_root + executable
            if binary_name in names:
                entry = archive.getinfo(binary_name)
                if entry.file_size <= _MAX_BINARY_BYTES:
                    binary_summary = parse_macho(archive.read(binary_name))
                else:
                    binary_summary = {"valid": False, "error": "binary exceeds size cap"}

        # Embedded frameworks (Frameworks/<Name>.framework/).
        framework_names: set[str] = set()
        for name in names:
            marker = app_root + "Frameworks/"
            if name.startswith(marker) and ".framework/" in name[len(marker):]:
                fw = name[len(marker):].split(".framework/", 1)[0]
                if fw:
                    framework_names.add(fw)

        # Privacy manifest (may live in the app root or inside a framework).
        privacy: dict[str, Any] = {"present": False}
        for name in names:
            if name.endswith("PrivacyInfo.xcprivacy"):
                privacy = analyze_privacy_manifest(archive.read(name))
                privacy["present"] = privacy.get("valid", False)
                privacy["path"] = name
                break

        tokens = set(framework_names)
        tokens.update(binary_summary.get("frameworks", []))
        detections = detect_ios(tokens)

        ats = info.get("NSAppTransportSecurity", {}) or {}
        findings: list[dict[str, Any]] = []
        if isinstance(ats, dict) and ats.get("NSAllowsArbitraryLoads"):
            findings.append(
                annotate(
                    {
                        "severity": "medium",
                        "category": "ios-transport-security",
                        "evidence": "NSAllowsArbitraryLoads=true",
                        "message": "App Transport Security allows arbitrary (insecure) loads",
                    }
                )
            )
        if binary_summary.get("valid"):
            if not binary_summary.get("pie"):
                findings.append(
                    annotate(
                        {
                            "severity": "medium",
                            "category": "ios-binary-protection",
                            "evidence": "MH_PIE flag absent",
                            "message": "binary is not position-independent (no PIE/ASLR)",
                        }
                    )
                )
            if not binary_summary.get("has_stack_canary"):
                findings.append(
                    annotate(
                        {
                            "severity": "low",
                            "category": "ios-binary-protection",
                            "evidence": "no stack canary symbols",
                            "message": "no stack-canary symbols detected in binary",
                        }
                    )
                )
        for pf in privacy.get("findings", []) if privacy.get("valid") else []:
            findings.append(
                annotate(
                    {
                        "severity": pf.get("severity", "low"),
                        "category": "manifest",
                        "evidence": "PrivacyInfo.xcprivacy",
                        "message": pf.get("message", ""),
                    }
                )
            )

    return {
        "platform": "ios",
        "path": str(ipa_path),
        "sha256": sha256_file(ipa_path),
        "size_bytes": ipa_path.stat().st_size,
        "app": {
            "bundle_id": info.get("CFBundleIdentifier", ""),
            "name": info.get("CFBundleDisplayName") or info.get("CFBundleName", ""),
            "version": info.get("CFBundleShortVersionString", ""),
            "build": info.get("CFBundleVersion", ""),
            "minimum_os": info.get("MinimumOSVersion", ""),
            "executable": executable,
            "platforms": info.get("CFBundleSupportedPlatforms", []),
        },
        "binary": binary_summary,
        "frameworks": sorted(framework_names),
        "privacy_manifest": privacy,
        "trackers": [d for d in detections if d["kind"] == "tracker"],
        "libraries": [d for d in detections if d["kind"] == "library"],
        "findings": findings,
    }


def is_ipa(path: Path) -> bool:
    """Return True when the file *is* an iOS application archive.

    Detection is content-based: a renamed ``.apk`` that is really an IPA is
    still routed to the iOS engine, and an ``.ipa`` that is really an Android
    package is not.
    """
    from apex.format_detect import detect_format

    path = Path(path)
    try:
        return detect_format(path).format == "ipa"
    except (FileNotFoundError, OSError):
        return posixpath.splitext(str(path).lower())[1] == ".ipa"
