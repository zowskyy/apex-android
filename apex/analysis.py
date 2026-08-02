"""Core APK analysis primitives used by the CLI, API, and web UI.

The native Rust ZIP reader remains the preferred extraction backend.  The
higher-level Android parsers use Androguard, which gives APEX production-grade
AXML/ARSC/DEX handling while the native parsers continue to mature.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

try:
    from loguru import logger

    logger.disable("androguard")
except Exception:  # pragma: no cover - logging is optional
    pass

try:
    from androguard.core.analysis.analysis import Analysis
    from androguard.core.axml import ARSCParser, AXMLPrinter
    from androguard.core.dex import DEX
    from androguard.decompiler.decompiler import DecompilerDAD
except Exception:  # pragma: no cover - surfaced as a backend error at runtime
    Analysis = ARSCParser = AXMLPrinter = DEX = DecompilerDAD = None

try:
    import apex_zip_reader as _native_zip
except Exception:  # pragma: no cover - pure Python fallback is tested
    _native_zip = None


MAX_ZIP_NAME = 4096
MAX_ENTRY_SIZE = 512 * 1024 * 1024
MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024
MAX_ENTRIES = 200_000
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


class ApexError(RuntimeError):
    """An actionable error suitable for showing directly to a CLI user."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitized_zip_name(raw_name: str) -> str | None:
    """Return a normalized relative ZIP path, or ``None`` when unsafe."""
    if not raw_name or len(raw_name) > MAX_ZIP_NAME or "\0" in raw_name:
        return None
    normalized = raw_name.replace("\\", "/")
    if normalized.startswith("/"):
        return None
    if len(normalized) >= 2 and normalized[0].isalpha() and normalized[1] == ":":
        return None
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _fallback_extract(apk_path: Path, extract_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total_size = 0
    with zipfile.ZipFile(apk_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ApexError(f"archive has {len(infos):,} entries; limit is {MAX_ENTRIES:,}")
        for info in infos:
            safe_name = sanitized_zip_name(info.filename)
            reason = ""
            if safe_name is None:
                reason = "unsafe path"
            elif info.file_size > MAX_ENTRY_SIZE:
                reason = f"entry exceeds {MAX_ENTRY_SIZE} byte limit"
            elif total_size + info.file_size > MAX_TOTAL_SIZE:
                reason = f"archive exceeds {MAX_TOTAL_SIZE} byte expansion limit"
            if reason:
                entries.append({"name": info.filename, "verdict": "WARN", "reason": reason})
                continue

            destination = extract_dir / safe_name
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
            total_size += info.file_size
            entries.append({"name": info.filename, "verdict": "CLEAN"})

    warned = sum(entry["verdict"] == "WARN" for entry in entries)
    return {
        "backend": "python",
        "total_entries": len(entries),
        "extracted": len(entries) - warned,
        "warned": warned,
        "entries": entries,
        "uncompressed_bytes": total_size,
    }


def extract_apk(apk_path: Path, work_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Safely extract an APK and return ``(directory, security_report)``."""
    apk_path = Path(apk_path)
    if not apk_path.is_file():
        raise ApexError(f"APK not found: {apk_path}")
    extract_dir = Path(work_dir) / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    if _native_zip is not None:
        try:
            report = dict(_native_zip.extract_apk(str(apk_path), str(extract_dir)))
            report["backend"] = "rust"
            return extract_dir, report
        except Exception as exc:
            raise ApexError(f"secure ZIP extraction failed: {exc}") from exc
    try:
        return extract_dir, _fallback_extract(apk_path, extract_dir)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ApexError(f"invalid APK/ZIP: {exc}") from exc


def inventory_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def _xml_bytes(raw: bytes) -> bytes:
    stripped = raw.lstrip()
    if stripped.startswith(b"<"):
        return raw
    if AXMLPrinter is None:
        raise ApexError("binary XML requires the 'androguard' dependency")
    return AXMLPrinter(raw).get_xml(pretty=True)


def decode_binary_xml(raw: bytes) -> str:
    """Decode Android binary XML, accepting ordinary XML as well."""
    return _xml_bytes(raw).decode("utf-8", errors="replace")


def _manifest_summary(raw: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "package": "",
        "version_code": "",
        "version_name": "",
        "min_sdk": "",
        "target_sdk": "",
        "permissions": [],
        "activities": [],
        "services": [],
        "receivers": [],
        "providers": [],
        "main_activity": "",
        "debuggable": False,
        "uses_cleartext_traffic": False,
        "allow_backup": True,
    }
    try:
        root = ET.fromstring(_xml_bytes(raw))
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result.update(
        {
            "package": root.attrib.get("package", ""),
            "version_code": root.attrib.get(f"{ANDROID_NS}versionCode", ""),
            "version_name": root.attrib.get(f"{ANDROID_NS}versionName", ""),
        }
    )
    sdk = root.find("uses-sdk")
    if sdk is not None:
        result["min_sdk"] = sdk.attrib.get(f"{ANDROID_NS}minSdkVersion", "")
        result["target_sdk"] = sdk.attrib.get(f"{ANDROID_NS}targetSdkVersion", "")
    result["permissions"] = sorted(
        {
            node.attrib.get(f"{ANDROID_NS}name", "")
            for node in root.findall("uses-permission")
            if node.attrib.get(f"{ANDROID_NS}name")
        }
    )
    application = root.find("application")
    if application is None:
        return result
    result["debuggable"] = (
        application.attrib.get(f"{ANDROID_NS}debuggable", "false").lower() == "true"
    )
    result["uses_cleartext_traffic"] = (
        application.attrib.get(f"{ANDROID_NS}usesCleartextTraffic", "false").lower() == "true"
    )
    result["allow_backup"] = (
        application.attrib.get(f"{ANDROID_NS}allowBackup", "true").lower() == "true"
    )

    component_map = {
        "activity": "activities",
        "activity-alias": "activities",
        "service": "services",
        "receiver": "receivers",
        "provider": "providers",
    }
    package = str(result["package"])
    for tag, key in component_map.items():
        for node in application.findall(tag):
            name = node.attrib.get(f"{ANDROID_NS}name", "")
            if name.startswith("."):
                name = package + name
            elif name and "." not in name and package:
                name = f"{package}.{name}"
            if name:
                result[key].append(name)
            for intent in node.findall("intent-filter"):
                actions = {
                    action.attrib.get(f"{ANDROID_NS}name") for action in intent.findall("action")
                }
                categories = {
                    category.attrib.get(f"{ANDROID_NS}name")
                    for category in intent.findall("category")
                }
                if (
                    "android.intent.action.MAIN" in actions
                    and "android.intent.category.LAUNCHER" in categories
                ):
                    result["main_activity"] = name
    for key in component_map.values():
        result[key] = sorted(set(result[key]))
    return result


def resource_table_info(raw: bytes) -> dict[str, Any]:
    """Return a bounded summary of an Android ``resources.arsc`` table."""
    summary: dict[str, Any] = {
        "size_bytes": len(raw),
        "packages": [],
        "locales": [],
        "types": [],
    }
    if not raw:
        return summary
    if ARSCParser is None:
        summary["error"] = "androguard backend unavailable"
        return summary
    try:
        parser = ARSCParser(raw)
        packages = list(parser.get_packages_names())
        locales: set[str] = set()
        types: set[str] = set()
        for package in packages:
            for locale in parser.get_locales(package):
                if isinstance(locale, bytes):
                    locale = locale.decode(errors="replace")
                locales.add(str(locale))
            for resource_type in parser.get_types(package):
                types.add(str(resource_type))
        summary.update(
            {
                "packages": sorted(map(str, packages)),
                "locales": sorted(locales),
                "types": sorted(types),
            }
        )
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


def scan_resources(extract_dir: Path) -> dict[str, Any]:
    manifest = extract_dir / "AndroidManifest.xml"
    resources = extract_dir / "resources.arsc"
    result: dict[str, Any] = {
        "manifest_present": manifest.is_file(),
        "resources_arsc_present": resources.is_file(),
        "manifest": _manifest_summary(manifest.read_bytes()) if manifest.is_file() else {},
        "resource_table": resource_table_info(resources.read_bytes())
        if resources.is_file()
        else {},
        "res_files": inventory_files(extract_dir / "res") if (extract_dir / "res").is_dir() else [],
        "asset_files": inventory_files(extract_dir / "assets")
        if (extract_dir / "assets").is_dir()
        else [],
    }
    # Compatibility with the original report schema.
    result["manifest_xml"] = result["manifest"]
    return result


def scan_native_libs(extract_dir: Path, keep_abi: list[str] | None = None) -> dict[str, Any]:
    libraries: list[dict[str, Any]] = []
    root = extract_dir / "lib"
    if root.is_dir():
        for abi_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if keep_abi and abi_dir.name not in keep_abi:
                continue
            for library in sorted(abi_dir.rglob("*.so")):
                libraries.append(
                    {
                        "abi": abi_dir.name,
                        "path": library.relative_to(extract_dir).as_posix(),
                        "size": library.stat().st_size,
                        "sha256": sha256_file(library),
                    }
                )
    return {"native_libs": libraries}


def descriptor_to_java(descriptor: str) -> str:
    if descriptor.startswith("L") and descriptor.endswith(";"):
        return descriptor[1:-1].replace("/", ".")
    primitives = {
        "V": "void",
        "Z": "boolean",
        "B": "byte",
        "S": "short",
        "C": "char",
        "I": "int",
        "J": "long",
        "F": "float",
        "D": "double",
    }
    if descriptor.startswith("["):
        return descriptor_to_java(descriptor[1:]) + "[]"
    return primitives.get(descriptor, descriptor)


def load_dex(raw: bytes, with_decompiler: bool = False) -> tuple[Any, Any]:
    if DEX is None or Analysis is None:
        raise ApexError("DEX analysis requires the 'androguard' dependency")
    dex = DEX(raw)
    analysis = Analysis(dex)
    analysis.create_xref()
    if with_decompiler and DecompilerDAD is not None:
        dex.set_decompiler(DecompilerDAD(dex, analysis))
    return dex, analysis


def dex_metadata(raw: bytes, dex_name: str = "classes.dex") -> dict[str, Any]:
    dex, analysis = load_dex(raw)
    classes: list[dict[str, Any]] = []
    methods: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for cls in dex.get_classes():
        descriptor = str(cls.get_name())
        class_name = descriptor_to_java(descriptor)
        classes.append(
            {
                "dex": dex_name,
                "name": class_name,
                "descriptor": descriptor,
                "super": descriptor_to_java(str(cls.get_superclassname() or "")),
                "interfaces": [descriptor_to_java(str(item)) for item in cls.get_interfaces()],
                "access": cls.get_access_flags_string(),
                "source_file_index": int(cls.get_source_file_idx()),
            }
        )
        for method in cls.get_methods():
            code = method.get_code()
            methods.append(
                {
                    "dex": dex_name,
                    "class": class_name,
                    "name": str(method.get_name()),
                    "descriptor": str(method.get_descriptor()),
                    "access": method.get_access_flags_string(),
                    "has_code": code is not None,
                    "instruction_count": (
                        sum(1 for _ in method.get_instructions()) if code is not None else 0
                    ),
                }
            )

    for method_analysis in analysis.get_methods():
        source = descriptor_to_java(str(method_analysis.class_name))
        source_method = str(method_analysis.name)
        for _, target, offset in method_analysis.get_xref_to():
            edges.append(
                {
                    "caller_class": source,
                    "caller_method": source_method,
                    "callee": (
                        f"{descriptor_to_java(str(target.class_name))}::{target.name}"
                        f"{target.descriptor}"
                    ),
                    "offset": int(offset),
                }
            )

    return {
        "dex": dex_name,
        "classes": classes,
        "methods": methods,
        "strings": [str(value) for value in dex.get_strings()[:50_000]],
        "edges": edges,
    }


def scan_dex_metadata(extract_dir: Path) -> dict[str, Any]:
    dex_files = sorted(extract_dir.glob("classes*.dex"))
    result: dict[str, Any] = {
        "dex_files": [path.name for path in dex_files],
        "classes": [],
        "methods": [],
        "strings": [],
        "edges": [],
        "errors": [],
    }
    for dex_path in dex_files:
        try:
            item = dex_metadata(dex_path.read_bytes(), dex_path.name)
            for key in ("classes", "methods", "strings", "edges"):
                result[key].extend(item[key])
        except Exception as exc:
            result["errors"].append({"dex": dex_path.name, "error": str(exc)})
            # Preserve discoverability for malformed/minimal fixtures.
            result["classes"].append(
                {"dex": dex_path.name, "name": dex_path.stem, "parse_error": str(exc)}
            )
    return result


def build_crossrefs(dex_index: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []
    for cls in dex_index.get("classes", []):
        if cls.get("name"):
            nodes[cls["name"]] = {"id": cls["name"], "kind": "class"}
    for method in dex_index.get("methods", []):
        if not method.get("class") or not method.get("name"):
            continue
        method_id = f"{method['class']}::{method['name']}{method.get('descriptor', '')}"
        nodes[method_id] = {"id": method_id, "kind": "method"}
        edges.append({"src": method["class"], "dst": method_id, "kind": "contains"})
    for edge in dex_index.get("edges", []):
        source = f"{edge.get('caller_class')}::{edge.get('caller_method')}"
        target = str(edge.get("callee", ""))
        if source and target:
            nodes.setdefault(source, {"id": source, "kind": "method"})
            nodes.setdefault(target, {"id": target, "kind": "method"})
            edges.append({"src": source, "dst": target, "kind": "calls"})
    return {"nodes": sorted(nodes.values(), key=lambda item: item["id"]), "edges": edges}


def build_reachability(
    dex_index: dict[str, Any],
    resource_index: dict[str, Any],
    native_index: dict[str, Any],
) -> dict[str, Any]:
    manifest = resource_index.get("manifest", {})
    manifest_entries = [
        manifest.get("main_activity", ""),
        *manifest.get("services", []),
        *manifest.get("receivers", []),
        *manifest.get("providers", []),
    ]
    heuristic_entries = [
        cls.get("name", "")
        for cls in dex_index.get("classes", [])
        if any(
            hint in cls.get("name", "").lower()
            for hint in ("mainactivity", "application", "service", "receiver", "provider")
        )
    ]
    entry_points = sorted({entry for entry in manifest_entries + heuristic_entries if entry})

    adjacency: dict[str, set[str]] = {}
    for edge in dex_index.get("edges", []):
        source = str(edge.get("caller_class", ""))
        target = str(edge.get("callee", "")).split("::", 1)[0]
        if source and target:
            adjacency.setdefault(source, set()).add(target)
    reachable = set(entry_points)
    pending = list(entry_points)
    while pending:
        current = pending.pop()
        for target in adjacency.get(current, set()):
            if target not in reachable:
                reachable.add(target)
                pending.append(target)

    return {
        "entry_points": entry_points,
        "reachable_nodes": sorted(reachable),
        "class_count": len(dex_index.get("classes", [])),
        "method_count": len(dex_index.get("methods", [])),
        "edge_count": len(dex_index.get("edges", [])),
        "native_count": len(native_index.get("native_libs", [])),
        "resource_count": len(resource_index.get("res_files", [])),
    }


def _zip_inventory_native(apk_path: Path) -> dict[str, Any] | None:
    """Fast columnar inventory via the Rust reader (one FFI crossing).

    Returns ``None`` when the native extension is unavailable so the caller can
    fall back to the pure-Python path.
    """
    if _native_zip is None or not hasattr(_native_zip, "read_inventory"):
        return None
    try:
        columns = _native_zip.read_inventory(str(apk_path))
    except Exception:
        return None
    names = columns["names"]
    sizes = columns["sizes"]
    compressed = columns["compressed_sizes"]
    crcs = columns["crc32"]
    safe = columns["safe"]
    files = [
        {
            "name": names[i],
            "size": sizes[i],
            "compressed_size": compressed[i],
            "crc32": f"{crcs[i]:08x}",
            "safe": bool(safe[i]),
        }
        for i in range(len(names))
    ]
    return {
        "entry_count": len(files),
        "uncompressed_bytes": sum(sizes),
        "compressed_bytes": sum(compressed),
        "files": files,
    }


def zip_inventory(apk_path: Path) -> dict[str, Any]:
    native = _zip_inventory_native(apk_path)
    if native is not None:
        return native
    files: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path) as archive:
        for info in archive.infolist():
            files.append(
                {
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "safe": sanitized_zip_name(info.filename) is not None,
                }
            )
    return {
        "entry_count": len(files),
        "uncompressed_bytes": sum(item["size"] for item in files),
        "compressed_bytes": sum(item["compressed_size"] for item in files),
        "files": files,
    }


def inspect_apk(apk_path: Path, include_files: bool = False) -> dict[str, Any]:
    """Fast, extraction-free APK/AAB/XAPK metadata inspection."""
    apk_path = Path(apk_path)
    if not apk_path.is_file():
        raise ApexError(f"APK not found: {apk_path}")
    inventory = zip_inventory(apk_path)
    with zipfile.ZipFile(apk_path) as archive:
        names = set(archive.namelist())
        manifest_name = next(
            (
                candidate
                for candidate in ("AndroidManifest.xml", "base/manifest/AndroidManifest.xml")
                if candidate in names
            ),
            "",
        )
        manifest = _manifest_summary(archive.read(manifest_name)) if manifest_name else {}
        resource_table = (
            resource_table_info(archive.read("resources.arsc")) if "resources.arsc" in names else {}
        )
        dex_files = sorted(
            name
            for name in names
            if Path(name).name.startswith("classes") and name.endswith(".dex")
        )
    result = {
        "format": apk_path.suffix.lower().lstrip(".") or "zip",
        "path": str(apk_path),
        "sha256": sha256_file(apk_path),
        "size_bytes": apk_path.stat().st_size,
        "manifest": manifest,
        "resource_table": resource_table,
        "dex_files": dex_files,
        "split_apks": sorted(name for name in names if name.lower().endswith(".apk")),
        "entry_count": inventory["entry_count"],
        "uncompressed_bytes": inventory["uncompressed_bytes"],
        "native_abis": sorted(
            {
                parts[index + 1]
                for item in inventory["files"]
                for parts in [item["name"].split("/")]
                for index, part in enumerate(parts[:-1])
                if part == "lib" and index + 2 < len(parts)
            }
        ),
        "unsafe_entries": [item["name"] for item in inventory["files"] if not item["safe"]],
    }
    if include_files:
        result["files"] = inventory["files"]
    return result


def export_minimal_bundle(
    extract_dir: Path, out_dir: Path, keep_abi: list[str] | None = None
) -> dict[str, Any]:
    export_dir = out_dir / "bundle"
    export_dir.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    for relative in ("AndroidManifest.xml", "resources.arsc"):
        source = extract_dir / relative
        if source.is_file():
            shutil.copy2(source, export_dir / relative)
            kept.append(relative)
    for folder in ("res", "assets"):
        source = extract_dir / folder
        if source.is_dir():
            shutil.copytree(source, export_dir / folder, dirs_exist_ok=True)
            kept.append(folder)
    libraries = extract_dir / "lib"
    if libraries.is_dir():
        for abi_dir in sorted(path for path in libraries.iterdir() if path.is_dir()):
            if keep_abi and abi_dir.name not in keep_abi:
                continue
            shutil.copytree(abi_dir, export_dir / "lib" / abi_dir.name, dirs_exist_ok=True)
            kept.append(f"lib/{abi_dir.name}")
    for dex_file in sorted(extract_dir.glob("classes*.dex")):
        shutil.copy2(dex_file, export_dir / dex_file.name)
        kept.append(dex_file.name)
    data = {"export_dir": str(export_dir), "kept": kept}
    (out_dir / "export_index.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def diff_indexes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_classes = {item.get("name") for item in left.get("classes", []) if item.get("name")}
    right_classes = {item.get("name") for item in right.get("classes", []) if item.get("name")}
    left_methods = {
        f"{item.get('class')}::{item.get('name')}{item.get('descriptor', '')}"
        for item in left.get("methods", [])
        if item.get("class") and item.get("name")
    }
    right_methods = {
        f"{item.get('class')}::{item.get('name')}{item.get('descriptor', '')}"
        for item in right.get("methods", [])
        if item.get("class") and item.get("name")
    }
    return {
        "classes_added": sorted(right_classes - left_classes),
        "classes_removed": sorted(left_classes - right_classes),
        "methods_added": sorted(right_methods - left_methods),
        "methods_removed": sorted(left_methods - right_methods),
        "dex_files_added": sorted(set(right.get("dex_files", [])) - set(left.get("dex_files", []))),
        "dex_files_removed": sorted(
            set(left.get("dex_files", [])) - set(right.get("dex_files", []))
        ),
    }
