from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from . import native


ARSC_SUSPICIOUS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\.\.[/\\]",
        r"%2e%2e",
        r"file://",
        r"https?://",
        r"/data/data/",
        r"/system/(?:bin|xbin)/",
        r"\b(?:su|busybox|frida|xposed|magisk)\b",
    )
]

TRAVERSAL_ONLY = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(^|[^/])\.\.[/\\]",
        r"%2e%2e",
    )
]


def _json_default(value: Any) -> str:
    return str(value)


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, separators=(",", ":"), default=_json_default))


def _columnar_entries(apk_path: Path) -> dict[str, list[Any]]:
    return dict(native.zip_reader().read_entries_columnar(str(apk_path)))


def _entry_names(entries: dict[str, list[Any]]) -> list[str]:
    return [str(name) for name in entries.get("names", [])]


def _entry_sizes(entries: dict[str, list[Any]], key: str) -> int:
    return sum(int(size or 0) for size in entries.get(key, []))


def _read_entries(apk_path: Path, names: list[str]) -> dict[str, bytes]:
    if not names:
        return {}
    return dict(native.zip_reader().read_entries_data(str(apk_path), names))


def _decode_manifest(data: bytes) -> dict[str, Any]:
    arsc = native.arsc_parser()
    try:
        xml = arsc.decode_axml(data) if arsc.is_binary_xml(data) else data.decode("utf-8", "replace")
    except Exception as exc:
        return {"decoded": False, "error": str(exc)}

    package_match = re.search(r'\bpackage="([^"]+)"', xml)
    min_sdk_match = re.search(r'\bandroid:minSdkVersion="([^"]+)"', xml)
    target_sdk_match = re.search(r'\bandroid:targetSdkVersion="([^"]+)"', xml)
    return {
        "decoded": True,
        "package": package_match.group(1) if package_match else "",
        "min_sdk": min_sdk_match.group(1) if min_sdk_match else "",
        "target_sdk": target_sdk_match.group(1) if target_sdk_match else "",
        "xml_bytes": len(xml.encode("utf-8")),
    }


def _arsc_summary(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    try:
        return dict(native.arsc_parser().arsc_summary(data))
    except Exception as exc:
        return {"error": str(exc)}


def _dex_summary(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    try:
        summary = dict(native.dex_parser().dex_summary(data))
        return {
            "class_count": summary.get("class_count", 0),
            "method_count": summary.get("method_count", 0),
            "string_count": summary.get("string_count", 0),
        }
    except Exception as exc:
        return {"error": str(exc)}


def inspect_apk(apk_path: Path) -> dict[str, Any]:
    """Fast APK overview: central-directory scan plus manifest/arsc/first DEX."""
    started = time.perf_counter()
    apk_path = Path(apk_path)
    entries = _columnar_entries(apk_path)
    names = _entry_names(entries)
    dex_names = sorted(name for name in names if re.fullmatch(r"classes(?:\d*)\.dex", Path(name).name))
    selected = [name for name in ("AndroidManifest.xml", "resources.arsc") if name in names]
    if dex_names:
        selected.append(dex_names[0])
    data = _read_entries(apk_path, selected)

    clean = sum(1 for verdict in entries.get("verdicts", []) if verdict == "CLEAN")
    warned = sum(1 for verdict in entries.get("verdicts", []) if verdict == "WARN")
    result = {
        "apk": str(apk_path),
        "size_bytes": apk_path.stat().st_size,
        "zip": {
            "entries": len(names),
            "clean": clean,
            "warned": warned,
            "compressed_bytes": _entry_sizes(entries, "compressed_sizes"),
            "uncompressed_bytes": _entry_sizes(entries, "uncompressed_sizes"),
            "dex_files": dex_names,
            "native_libs": sum(1 for name in names if name.startswith("lib/") and name.endswith(".so")),
            "resource_files": sum(1 for name in names if name.startswith("res/")),
        },
        "manifest": _decode_manifest(data.get("AndroidManifest.xml", b""))
        if "AndroidManifest.xml" in data
        else {"decoded": False, "missing": True},
        "resources": _arsc_summary(data.get("resources.arsc", b"")),
        "dex": _dex_summary(data.get(dex_names[0], b"")) if dex_names else {},
    }
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _safe_java_path(root: Path, class_name: str) -> Path:
    parts = [part for part in class_name.replace("$", ".").split(".") if part]
    if not parts:
        parts = ["UnknownClass"]
    safe_parts = [re.sub(r"[^A-Za-z0-9_]", "_", part) for part in parts]
    return root.joinpath(*safe_parts).with_suffix(".java")


def _decompile_dex_to_dir(dex_name: str, dex_data: bytes, java_dir: Path) -> int:
    classes = native.dex_parser().decompile_dex(dex_data)
    count = 0
    for idx, (class_name, java) in enumerate(classes):
        target = _safe_java_path(java_dir, str(class_name) or f"{Path(dex_name).stem}_{idx}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(java), encoding="utf-8")
        count += 1
    return count


def decompile_apk(apk_path: Path, out_dir: Path, first_dex_only: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    apk_path = Path(apk_path)
    out_dir = Path(out_dir)
    java_dir = out_dir / "java"
    if java_dir.exists():
        shutil.rmtree(java_dir)
    java_dir.mkdir(parents=True, exist_ok=True)

    names = _entry_names(_columnar_entries(apk_path))
    dex_names = sorted(name for name in names if re.fullmatch(r"classes(?:\d*)\.dex", Path(name).name))
    if first_dex_only and dex_names:
        dex_names = dex_names[:1]
    dex_data = _read_entries(apk_path, dex_names)
    class_count = 0
    for dex_name in dex_names:
        class_count += _decompile_dex_to_dir(dex_name, dex_data[dex_name], java_dir)
    return {
        "apk": str(apk_path),
        "out_dir": str(out_dir),
        "java_dir": str(java_dir),
        "dex_files": dex_names,
        "classes": class_count,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _decode_xml_files(root: Path) -> int:
    arsc = native.arsc_parser()
    decoded = 0
    for path in sorted(root.rglob("*.xml")):
        data = path.read_bytes()
        if not arsc.is_binary_xml(data):
            continue
        path.write_text(arsc.decode_axml(data), encoding="utf-8")
        decoded += 1
    return decoded


def decode_apk(apk_path: Path, out_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    apk_path = Path(apk_path)
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    extract_report = dict(native.zip_reader().extract_apk(str(apk_path), str(out_dir)))
    decoded_xml = _decode_xml_files(out_dir)
    decompile_report = decompile_apk(apk_path, out_dir)
    return {
        "apk": str(apk_path),
        "out_dir": str(out_dir),
        "zip": {
            "entries": extract_report.get("total_entries"),
            "extracted": extract_report.get("extracted"),
            "warned": extract_report.get("warned"),
        },
        "decoded_xml": decoded_xml,
        "decompile": decompile_report,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _matches(patterns: list[re.Pattern[str]], values: list[str]) -> list[dict[str, str]]:
    findings = []
    for value in values:
        for pattern in patterns:
            if pattern.search(value):
                findings.append({"pattern": pattern.pattern, "value": value})
                break
    return findings


def security_scan_apk(apk_path: Path) -> dict[str, Any]:
    apk_path = Path(apk_path)
    entries = _columnar_entries(apk_path)
    names = _entry_names(entries)
    selected = [name for name in ("AndroidManifest.xml", "resources.arsc") if name in names]
    data = _read_entries(apk_path, selected)

    arsc = native.arsc_parser()
    manifest_strings: list[str] = []
    if "AndroidManifest.xml" in data:
        try:
            manifest_strings = arsc.axml_strings(data["AndroidManifest.xml"])
        except Exception:
            manifest_strings = []

    arsc_strings: list[str] = []
    if "resources.arsc" in data:
        try:
            arsc_strings = arsc.scan_string_pools(data["resources.arsc"])
        except Exception:
            arsc_strings = []

    zip_warnings = []
    for idx, verdict in enumerate(entries.get("verdicts", [])):
        if verdict == "WARN":
            zip_warnings.append(
                {
                    "name": names[idx],
                    "reason": entries.get("reasons", [""] * len(names))[idx],
                }
            )

    return {
        "apk": str(apk_path),
        "zip_warnings": zip_warnings,
        "manifest_traversal": _matches(TRAVERSAL_ONLY, manifest_strings),
        "resource_findings": _matches(ARSC_SUSPICIOUS, arsc_strings),
    }


def cmd_inspect(args: Any) -> None:
    _print_json(inspect_apk(Path(args.apk)))


def cmd_decompile(args: Any) -> None:
    _print_json(decompile_apk(Path(args.apk), Path(args.out), first_dex_only=args.first_dex_only))


def cmd_decode(args: Any) -> None:
    _print_json(decode_apk(Path(args.apk), Path(args.out)))


def cmd_security_scan(args: Any) -> None:
    _print_json(security_scan_apk(Path(args.apk)))


def add_cli_commands(sub: Any) -> None:
    inspect = sub.add_parser("inspect", help="Fast APK overview without extraction")
    inspect.add_argument("apk")
    inspect.set_defaults(func=cmd_inspect)

    decompile = sub.add_parser("decompile", help="Decompile APK DEX files to Java")
    decompile.add_argument("apk")
    decompile.add_argument("--out", default="apex_out", help="Output directory")
    decompile.add_argument("--first-dex-only", action="store_true", help="Benchmark helper: decompile only the first DEX")
    decompile.set_defaults(func=cmd_decompile)

    decode = sub.add_parser("decode", help="Extract, decode binary XML, and decompile DEX")
    decode.add_argument("apk")
    decode.add_argument("--out", default="apex_out", help="Output directory")
    decode.set_defaults(func=cmd_decode)

    scan = sub.add_parser("security-scan", help="Scan ZIP/resource strings for common APK risks")
    scan.add_argument("apk")
    scan.set_defaults(func=cmd_security_scan)


__all__ = [
    "inspect_apk",
    "decompile_apk",
    "decode_apk",
    "security_scan_apk",
    "cmd_inspect",
    "cmd_decompile",
    "cmd_decode",
    "cmd_security_scan",
    "add_cli_commands",
]
