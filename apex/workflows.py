"""User-facing APEX workflows.

Every operation is available as a Python function and a CLI command.  External
Android tools are optional: APEX performs safe, lossless raw decode/build on
its own and uses apktool/apksigner when the caller explicitly selects them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Iterator

from jinja2 import Template

from .analysis import (
    ANDROID_NS,
    ApexError,
    build_crossrefs,
    build_reachability,
    decode_binary_xml,
    descriptor_to_java,
    dex_metadata,
    diff_indexes,
    export_minimal_bundle,
    extract_apk,
    inspect_apk,
    inventory_files,
    load_dex,
    resource_table_info,
    sanitized_zip_name,
    scan_dex_metadata,
    scan_native_libs,
    scan_resources,
    sha256_file,
    zip_inventory,
)
from .version import __version__


class Store:
    def put(self, name: str, data: dict[str, Any]) -> None:
        raise NotImplementedError


class SQLiteStore(Store):
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS kv (name TEXT PRIMARY KEY, json TEXT NOT NULL)"
        )
        self.conn.commit()

    def put(self, name: str, data: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO kv(name, json) VALUES (?, ?)",
            (name, json.dumps(data)),
        )
        self.conn.commit()


class PostgresStore(Store):
    def __init__(self, dsn: str):
        from .edition import Feature, require_feature

        require_feature(Feature.POSTGRES_STORE)
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - optional integration
            raise ApexError("PostgreSQL storage requires 'psycopg'") from exc
        self.conn = psycopg.connect(dsn)
        with self.conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS kv (name TEXT PRIMARY KEY, json JSONB NOT NULL)"
            )
        self.conn.commit()

    def put(self, name: str, data: dict[str, Any]) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO kv(name, json) VALUES (%s, %s) "
                "ON CONFLICT (name) DO UPDATE SET json = EXCLUDED.json",
                (name, json.dumps(data)),
            )
        self.conn.commit()


REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>APEX report — {{ meta.name }}</title>
<style>
:root{color-scheme:dark;--bg:#080d18;--panel:#111a2b;--line:#24324a;--text:#e7edf7;--muted:#98a8c0;--accent:#6ee7ff}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui;background:var(--bg);color:var(--text)}
main{max-width:1180px;margin:auto;padding:32px}h1{font-size:32px;margin:0}h2{color:var(--accent);font-size:18px}
.sub{color:var(--muted);word-break:break-all}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:24px 0}
.card,section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}.value{font-size:28px;font-weight:700}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid var(--line)}code{color:#b7f5ff}
.ok{color:#8df5ad}.warn{color:#ffd079}details{margin:8px 0}.pill{display:inline-block;background:#1b2a42;padding:3px 9px;border-radius:999px;margin:3px}
</style></head>
<body><main>
<h1>APEX analysis</h1><div class="sub">{{ meta.path }} · {{ meta.sha256 }}</div>
<div class="grid">
<div class="card"><div class="value">{{ reach.class_count }}</div><div>classes</div></div>
<div class="card"><div class="value">{{ reach.method_count }}</div><div>methods</div></div>
<div class="card"><div class="value">{{ resources.res_files|length }}</div><div>resources</div></div>
<div class="card"><div class="value">{{ native.native_libs|length }}</div><div>native libraries</div></div>
</div>
<section><h2>Application</h2>
<table><tr><th>Package</th><td><code>{{ manifest.package or "unknown" }}</code></td></tr>
<tr><th>Version</th><td>{{ manifest.version_name }} ({{ manifest.version_code }})</td></tr>
<tr><th>SDK</th><td>min {{ manifest.min_sdk or "?" }} · target {{ manifest.target_sdk or "?" }}</td></tr>
<tr><th>Main activity</th><td><code>{{ manifest.main_activity or "not declared" }}</code></td></tr></table></section>
<section><h2>Security</h2><p class="{{ 'ok' if security.zip_extraction.warned == 0 else 'warn' }}">
{{ security.zip_extraction.warned }} unsafe ZIP entries blocked; backend {{ security.zip_extraction.backend }}.</p></section>
<section><h2>Entry points</h2>{% for item in reach.entry_points %}<span class="pill">{{ item }}</span>{% else %}<p>None detected.</p>{% endfor %}</section>
<section><h2>DEX files</h2>{% for name in dex.dex_files %}<span class="pill">{{ name }}</span>{% endfor %}
{% if dex.errors %}<details><summary>Parser warnings ({{ dex.errors|length }})</summary><pre>{{ dex.errors|tojson(indent=2) }}</pre></details>{% endif %}</section>
</main></body></html>"""


def render_report(report: dict[str, Any]) -> str:
    return Template(REPORT_TEMPLATE).render(
        meta=report["meta"],
        manifest=report["resources"].get("manifest", {}),
        resources=report["resources"],
        native=report["native"],
        dex=report["dex"],
        reach=report["reachability"],
        security=report["security"],
    )


def analyze_apk(
    apk_path: Path,
    out_dir: Path,
    keep_abi: list[str] | None = None,
    store: Store | None = None,
) -> dict[str, Any]:
    apk_path, out_dir = Path(apk_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    extract_dir, zip_security = extract_apk(apk_path, out_dir / "work")
    resources = scan_resources(extract_dir)
    native = scan_native_libs(extract_dir, keep_abi)
    dex = scan_dex_metadata(extract_dir)
    crossrefs = build_crossrefs(dex)
    reachability = build_reachability(dex, resources, native)
    bundle = export_minimal_bundle(extract_dir, out_dir, keep_abi)
    report = {
        "schema_version": 2,
        "meta": {
            "name": apk_path.name,
            "path": str(apk_path),
            "sha256": sha256_file(apk_path),
            "size_bytes": apk_path.stat().st_size,
            "analyzed_at": int(time.time()),
        },
        "security": {
            "zip_extraction": {
                "backend": zip_security.get("backend"),
                "total_entries": zip_security.get("total_entries"),
                "extracted": zip_security.get("extracted"),
                "warned": zip_security.get("warned", 0),
                "warnings": [
                    item
                    for item in zip_security.get("entries", [])
                    if item.get("verdict") == "WARN"
                ],
            }
        },
        "resources": resources,
        "native": native,
        "dex": dex,
        "crossrefs": crossrefs,
        "reachability": reachability,
        "bundle": bundle,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "report.html").write_text(render_report(report), encoding="utf-8")
    if store:
        for name in ("meta", "resources", "native", "dex", "crossrefs", "reachability"):
            store.put(name, report[name])
    return report


# Backward-compatible public function name.
analyze = analyze_apk


def _safe_source_path(class_name: str, suffix: str) -> Path:
    cleaned = class_name.replace("$", "_").replace("/", ".").strip(".")
    parts = [re.sub(r"[^A-Za-z0-9_.-]", "_", part) for part in cleaned.split(".")]
    return Path(*parts).with_suffix(suffix)


def _method_smali(method: Any) -> str:
    lines = [
        f".method {method.get_access_flags_string()} {method.get_name()}{method.get_descriptor()}"
    ]
    if method.get_code() is None:
        lines.append(".end method")
        return "\n".join(lines) + "\n"
    offset = 0
    for instruction in method.get_instructions():
        lines.append(
            f"    {offset:04x}: {instruction.get_name()} {instruction.get_output()}".rstrip()
        )
        offset += instruction.get_length()
    lines.append(".end method")
    return "\n".join(lines) + "\n"


def _mapping_index(mapping_path: Path | None) -> dict[str, str]:
    if not mapping_path:
        return {}
    mapping: dict[str, str] = {}
    class_line = re.compile(r"^(\S.*?)\s+->\s+(\S+):$")
    for line in mapping_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = class_line.match(line)
        if match:
            original, obfuscated = match.groups()
            mapping[obfuscated] = original
    return mapping


def decompile_apk(
    apk_path: Path,
    out_dir: Path,
    mapping_path: Path | None = None,
    emit_smali: bool = True,
    max_classes: int | None = None,
) -> dict[str, Any]:
    """Decompiler DEX files to Java, with readable Dalvik fallback files."""
    from .device_profile import limits as device_limits

    apk_path, out_dir = Path(apk_path), Path(out_dir)
    if max_classes is None:
        max_classes = int(device_limits().get("max_decompile_classes", 50_000))
    java_dir, smali_dir = out_dir / "java", out_dir / "smali"
    java_dir.mkdir(parents=True, exist_ok=True)
    if emit_smali:
        smali_dir.mkdir(parents=True, exist_ok=True)
    mapping = _mapping_index(mapping_path)
    index: dict[str, Any] = {"apk": str(apk_path), "dex_files": [], "classes": [], "errors": []}

    with zipfile.ZipFile(apk_path) as archive:
        dex_names = sorted(
            name for name in archive.namelist() if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name)
        )
        for dex_name in dex_names:
            try:
                lightweight = bool(device_limits().get("dex_lightweight"))
                dex, _ = load_dex(
                    archive.read(dex_name),
                    with_decompiler=True,
                    lightweight=lightweight,
                )
            except Exception as exc:
                index["errors"].append({"dex": dex_name, "error": str(exc)})
                continue
            index["dex_files"].append(dex_name)
            for cls in dex.get_classes():
                if len(index["classes"]) >= max_classes:
                    index["errors"].append(
                        {
                            "dex": dex_name,
                            "error": f"decompile capped at {max_classes:,} classes for this device tier",
                        }
                    )
                    break
                descriptor = str(cls.get_name())
                obfuscated = descriptor_to_java(descriptor)
                display_name = mapping.get(obfuscated, obfuscated)
                class_entry: dict[str, Any] = {
                    "dex": dex_name,
                    "name": display_name,
                    "obfuscated_name": obfuscated if display_name != obfuscated else "",
                }
                try:
                    source = cls.get_source()
                    destination = java_dir / _safe_source_path(display_name, ".java")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(source, encoding="utf-8")
                    class_entry["java"] = destination.relative_to(out_dir).as_posix()
                except Exception as exc:
                    class_entry["decompile_error"] = str(exc)
                if emit_smali:
                    destination = smali_dir / _safe_source_path(display_name, ".smali")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    header = f".class {cls.get_access_flags_string()} {descriptor}\n"
                    header += f".super {cls.get_superclassname()}\n\n"
                    body = "".join(_method_smali(method) + "\n" for method in cls.get_methods())
                    destination.write_text(header + body, encoding="utf-8")
                    class_entry["smali"] = destination.relative_to(out_dir).as_posix()
                index["classes"].append(class_entry)
    (out_dir / "decompile-index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def _command_path(name: str, env_name: str | None = None) -> str | None:
    if env_name and os.environ.get(env_name):
        value = os.environ[env_name]
        return value if Path(value).exists() else None
    return shutil.which(name)


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _apktool_command() -> list[str] | None:
    executable = _command_path("apktool", "APEX_APKTOOL")
    if executable:
        return [executable]
    jar = os.environ.get("APEX_APKTOOL_JAR")
    if jar and Path(jar).is_file() and shutil.which("java"):
        return [shutil.which("java") or "java", "-jar", jar]
    return None


def decode_apk(apk_path: Path, out_dir: Path, backend: str = "auto") -> dict[str, Any]:
    """Decode an APK with apktool or APEX's lossless raw backend."""
    apk_path, out_dir = Path(apk_path), Path(out_dir)
    tool = _apktool_command()
    selected = ("apktool" if tool else "raw") if backend == "auto" else backend
    if selected not in {"raw", "apktool"}:
        raise ApexError("decode backend must be one of: auto, raw, apktool")
    if selected == "apktool":
        if not tool:
            raise ApexError(
                "apktool backend requested but not found; install apktool or set APEX_APKTOOL_JAR"
            )
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        result = _run([*tool, "d", "-f", str(apk_path), "-o", str(out_dir)])
        if result.returncode:
            raise ApexError(f"apktool decode failed:\n{(result.stdout + result.stderr)[-3000:]}")
        metadata = {
            "schema_version": 1,
            "backend": "apktool",
            "source_apk": str(apk_path.resolve()),
            "source_sha256": sha256_file(apk_path),
        }
        (out_dir / "apex-project.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata

    out_dir.mkdir(parents=True, exist_ok=True)
    staging, report = extract_apk(apk_path, out_dir / ".apex-staging")
    raw_dir = out_dir / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    shutil.move(str(staging), raw_dir)
    shutil.rmtree(out_dir / ".apex-staging", ignore_errors=True)
    decoded_dir = out_dir / "decoded"
    decoded_dir.mkdir(exist_ok=True)

    decoded_files: list[str] = []
    resource_xml = [
        f"res/{relative}"
        for relative in inventory_files(raw_dir / "res")
        if relative.lower().endswith(".xml")
    ]
    for relative in ["AndroidManifest.xml", *resource_xml]:
        source = raw_dir / relative
        if not source.is_file() or source.suffix.lower() != ".xml":
            continue
        try:
            text = decode_binary_xml(source.read_bytes())
        except Exception:
            continue
        destination = decoded_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        decoded_files.append(relative)
    arsc = raw_dir / "resources.arsc"
    if arsc.is_file():
        (decoded_dir / "resources-index.json").write_text(
            json.dumps(resource_table_info(arsc.read_bytes()), indent=2), encoding="utf-8"
        )

    with zipfile.ZipFile(apk_path) as archive:
        compression = {
            info.filename: info.compress_type
            for info in archive.infolist()
            if sanitized_zip_name(info.filename)
        }
    metadata = {
        "schema_version": 1,
        "backend": "raw",
        "source_apk": str(apk_path.resolve()),
        "source_sha256": sha256_file(apk_path),
        "raw_dir": "raw",
        "decoded_dir": "decoded",
        "decoded_files": decoded_files,
        "compression": compression,
        "security": {
            "blocked_entries": [
                item for item in report.get("entries", []) if item.get("verdict") == "WARN"
            ]
        },
        "note": (
            "Edit files under raw/ for lossless rebuild. decoded/ is a readable view; "
            "changed binary XML requires the apktool backend to recompile."
        ),
    }
    (out_dir / "apex-project.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _sign_apk(
    apk_path: Path,
    keystore: Path,
    alias: str,
    storepass: str,
    keypass: str | None = None,
) -> None:
    apksigner = _command_path("apksigner", "APEX_APKSIGNER")
    if not apksigner:
        raise ApexError("apksigner not found; install Android build-tools or set APEX_APKSIGNER")
    command = [
        apksigner,
        "sign",
        "--ks",
        str(keystore),
        "--ks-key-alias",
        alias,
        "--ks-pass",
        f"pass:{storepass}",
    ]
    if keypass:
        command.extend(["--key-pass", f"pass:{keypass}"])
    command.append(str(apk_path))
    result = _run(command)
    if result.returncode:
        raise ApexError(f"APK signing failed:\n{(result.stdout + result.stderr)[-3000:]}")


def build_project(
    project_dir: Path,
    output_apk: Path,
    *,
    sign_keystore: Path | None = None,
    sign_alias: str = "androiddebugkey",
    storepass: str = "android",
    keypass: str | None = None,
) -> dict[str, Any]:
    project_dir, output_apk = Path(project_dir), Path(output_apk)
    metadata_path = project_dir / "apex-project.json"
    if not metadata_path.is_file():
        raise ApexError(f"not an APEX project (missing {metadata_path})")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    backend = metadata.get("backend")
    output_apk.parent.mkdir(parents=True, exist_ok=True)
    if backend == "apktool":
        tool = _apktool_command()
        if not tool:
            raise ApexError("this project requires apktool; install it or set APEX_APKTOOL_JAR")
        result = _run([*tool, "b", str(project_dir), "-o", str(output_apk)])
        if result.returncode:
            raise ApexError(f"apktool build failed:\n{(result.stdout + result.stderr)[-3000:]}")
    elif backend == "raw":
        raw_dir = project_dir / metadata.get("raw_dir", "raw")
        if not raw_dir.is_dir():
            raise ApexError(f"raw project directory missing: {raw_dir}")
        compression: dict[str, int] = metadata.get("compression", {})
        with zipfile.ZipFile(output_apk, "w", allowZip64=True) as archive:
            for path in sorted(item for item in raw_dir.rglob("*") if item.is_file()):
                relative = path.relative_to(raw_dir).as_posix()
                if sanitized_zip_name(relative) is None:
                    raise ApexError(f"refusing unsafe project path: {relative}")
                archive.write(
                    path,
                    relative,
                    compress_type=int(compression.get(relative, zipfile.ZIP_DEFLATED)),
                    compresslevel=6,
                )
    else:
        raise ApexError(f"unsupported project backend: {backend!r}")
    if sign_keystore:
        _sign_apk(output_apk, sign_keystore, sign_alias, storepass, keypass)
    return {
        "output_apk": str(output_apk),
        "sha256": sha256_file(output_apk),
        "size_bytes": output_apk.stat().st_size,
        "backend": backend,
        "signed": sign_keystore is not None,
    }


def verify_apk(apk_path: Path) -> dict[str, Any]:
    apk_path = Path(apk_path)
    findings: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(apk_path) as archive:
            corrupt = archive.testzip()
            if corrupt:
                findings.append({"severity": "error", "message": f"CRC failure: {corrupt}"})
            names = archive.namelist()
            if (
                "AndroidManifest.xml" not in names
                and "base/manifest/AndroidManifest.xml" not in names
                and not any(name.lower().endswith(".apk") for name in names)
            ):
                findings.append({"severity": "error", "message": "AndroidManifest.xml is missing"})
            for name in names:
                if sanitized_zip_name(name) is None:
                    findings.append({"severity": "error", "message": f"unsafe ZIP path: {name}"})
            dex_results = {}
            for name in sorted(
                item for item in names if re.fullmatch(r"(?:.*/)?classes\d*\.dex", item)
            ):
                try:
                    item = dex_metadata(archive.read(name), name)
                    dex_results[name] = {
                        "valid": True,
                        "classes": len(item["classes"]),
                        "methods": len(item["methods"]),
                    }
                except Exception as exc:
                    dex_results[name] = {"valid": False, "error": str(exc)}
                    findings.append({"severity": "error", "message": f"{name}: {exc}"})
    except (OSError, zipfile.BadZipFile) as exc:
        return {"valid": False, "findings": [{"severity": "error", "message": str(exc)}]}

    signatures: dict[str, Any] = {"signed": False, "v1": False, "v2": False, "v3": False}
    try:
        from androguard.core.apk import APK

        parsed = APK(str(apk_path))
        signatures = {
            "signed": bool(parsed.is_signed()),
            "v1": bool(parsed.is_signed_v1()),
            "v2": bool(parsed.is_signed_v2()),
            "v3": bool(parsed.is_signed_v3()),
            "certificate_count": len(parsed.get_certificates()),
        }
    except Exception as exc:
        signatures["error"] = str(exc)
    return {
        "valid": not any(item["severity"] == "error" for item in findings),
        "apk": str(apk_path),
        "sha256": sha256_file(apk_path),
        "signatures": signatures,
        "dex": dex_results,
        "findings": findings,
    }


def _iter_arsc_strings(data: bytes) -> Iterator[tuple[int, str]]:
    """Bounded best-effort traversal of every ResStringPool in an ARSC file."""
    offset = 0
    while offset <= len(data) - 28:
        try:
            chunk_type, header_size, size = struct.unpack_from("<HHI", data, offset)
        except struct.error:
            return
        if (
            chunk_type != 0x0001
            or header_size < 28
            or size < header_size
            or offset + size > len(data)
        ):
            offset += 4
            continue
        try:
            string_count, _, flags, strings_start, _ = struct.unpack_from(
                "<IIIII", data, offset + 8
            )
            index_start = offset + header_size
            if string_count > 5_000_000 or index_start + string_count * 4 > offset + size:
                offset += 4
                continue
            utf8 = bool(flags & 0x100)
            base = offset + strings_start
            for index in range(string_count):
                entry_offset = struct.unpack_from("<I", data, index_start + index * 4)[0]
                position = base + entry_offset
                if position >= offset + size:
                    continue
                if utf8:
                    first = data[position]
                    position += 2 if first & 0x80 else 1
                    length_byte = data[position]
                    if length_byte & 0x80:
                        length = ((length_byte & 0x7F) << 8) | data[position + 1]
                        position += 2
                    else:
                        length = length_byte
                        position += 1
                    value = data[position : position + length].decode("utf-8", errors="replace")
                else:
                    length = struct.unpack_from("<H", data, position)[0]
                    position += 2
                    if length & 0x8000:
                        length = ((length & 0x7FFF) << 16) | struct.unpack_from(
                            "<H", data, position
                        )[0]
                        position += 2
                    value = data[position : position + length * 2].decode(
                        "utf-16-le", errors="replace"
                    )
                yield offset, value
        except (IndexError, struct.error):
            pass
        offset += max(4, size)


def security_scan(apk_path: Path) -> dict[str, Any]:
    apk_path = Path(apk_path)
    findings: list[dict[str, Any]] = []
    try:
        inventory = zip_inventory(apk_path)
        with zipfile.ZipFile(apk_path) as archive:
            names = set(archive.namelist())
            for item in inventory["files"]:
                if not item["safe"]:
                    findings.append(
                        {
                            "severity": "critical",
                            "category": "path-traversal",
                            "evidence": item["name"],
                            "message": "unsafe archive path would escape an extraction root",
                        }
                    )
                if item["size"] > 10 * 1024 * 1024 and item["compressed_size"]:
                    ratio = item["size"] / item["compressed_size"]
                    if ratio > 1000:
                        findings.append(
                            {
                                "severity": "high",
                                "category": "zip-bomb",
                                "evidence": item["name"],
                                "message": f"suspicious compression ratio ({ratio:.0f}:1)",
                            }
                        )
            if "resources.arsc" in names:
                patterns = (
                    re.compile(r"(?:^|[/\\])\.\.(?:[/\\]|$)"),
                    re.compile(r"^/"),
                    re.compile(r"^[A-Za-z]:\\"),
                    re.compile("\0"),
                )
                for pool_offset, value in _iter_arsc_strings(archive.read("resources.arsc")):
                    if any(pattern.search(value) for pattern in patterns):
                        findings.append(
                            {
                                "severity": "critical",
                                "category": "resource-path-traversal",
                                "evidence": value,
                                "pool_offset": pool_offset,
                                "message": "resource string contains an unsafe path",
                            }
                        )
            manifest_name = next(
                (
                    candidate
                    for candidate in ("AndroidManifest.xml", "base/manifest/AndroidManifest.xml")
                    if candidate in names
                ),
                "",
            )
            if manifest_name:
                from .analysis import _manifest_summary, _xml_bytes

                raw_manifest = archive.read(manifest_name)
                summary = _manifest_summary(raw_manifest)
                if summary.get("debuggable"):
                    findings.append(
                        {
                            "severity": "medium",
                            "category": "manifest",
                            "evidence": "android:debuggable=true",
                            "message": "application is debuggable",
                        }
                    )
                try:
                    import xml.etree.ElementTree as ET

                    root = ET.fromstring(_xml_bytes(raw_manifest))
                    application = root.find("application")
                    if application is not None:
                        if (
                            application.attrib.get(
                                f"{ANDROID_NS}usesCleartextTraffic", "false"
                            ).lower()
                            == "true"
                        ):
                            findings.append(
                                {
                                    "severity": "medium",
                                    "category": "manifest",
                                    "evidence": "android:usesCleartextTraffic=true",
                                    "message": "cleartext network traffic is permitted",
                                }
                            )
                        if (
                            application.attrib.get(f"{ANDROID_NS}allowBackup", "true").lower()
                            == "true"
                        ):
                            findings.append(
                                {
                                    "severity": "low",
                                    "category": "manifest",
                                    "evidence": "android:allowBackup=true/default",
                                    "message": "application data may be included in backups",
                                }
                            )
                except Exception:
                    pass
    except (OSError, zipfile.BadZipFile) as exc:
        return {
            "verdict": "INVALID",
            "apk": str(apk_path),
            "findings": [{"severity": "critical", "category": "archive", "message": str(exc)}],
        }

    from .secrets_scan import scan_apk_secrets

    for item in scan_apk_secrets(apk_path):
        findings.append(item)

    from .native_scan import scan_apk_native_libs

    for item in scan_apk_native_libs(apk_path):
        findings.append(item)

    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    highest = max((order[item["severity"]] for item in findings), default=0)
    verdict = "HIGH_RISK" if highest >= 3 else ("REVIEW" if findings else "CLEAN")
    return {
        "verdict": verdict,
        "apk": str(apk_path),
        "sha256": sha256_file(apk_path),
        "finding_count": len(findings),
        "findings": findings,
        "disclaimer": "Static indicators require human review; they are not a malware verdict.",
    }


def diff_apks(left: Path, right: Path) -> dict[str, Any]:
    left, right = Path(left), Path(right)
    left_zip, right_zip = zip_inventory(left), zip_inventory(right)
    left_files = {item["name"]: item for item in left_zip["files"]}
    right_files = {item["name"]: item for item in right_zip["files"]}
    common = set(left_files) & set(right_files)
    changed = sorted(
        name
        for name in common
        if (
            left_files[name]["crc32"],
            left_files[name]["size"],
        )
        != (
            right_files[name]["crc32"],
            right_files[name]["size"],
        )
    )
    left_dex = {"dex_files": [], "classes": [], "methods": []}
    right_dex = {"dex_files": [], "classes": [], "methods": []}
    with zipfile.ZipFile(left) as archive:
        for name in sorted(
            item for item in archive.namelist() if re.fullmatch(r"(?:.*/)?classes\d*\.dex", item)
        ):
            left_dex["dex_files"].append(name)
            try:
                metadata = dex_metadata(archive.read(name), name)
                left_dex["classes"].extend(metadata["classes"])
                left_dex["methods"].extend(metadata["methods"])
            except Exception:
                pass
    with zipfile.ZipFile(right) as archive:
        for name in sorted(
            item for item in archive.namelist() if re.fullmatch(r"(?:.*/)?classes\d*\.dex", item)
        ):
            right_dex["dex_files"].append(name)
            try:
                metadata = dex_metadata(archive.read(name), name)
                right_dex["classes"].extend(metadata["classes"])
                right_dex["methods"].extend(metadata["methods"])
            except Exception:
                pass
    return {
        "left": {"path": str(left), "sha256": sha256_file(left)},
        "right": {"path": str(right), "sha256": sha256_file(right)},
        "files": {
            "added": sorted(set(right_files) - set(left_files)),
            "removed": sorted(set(left_files) - set(right_files)),
            "changed": changed,
        },
        "dex": diff_indexes(left_dex, right_dex),
        "identical": sha256_file(left) == sha256_file(right),
    }


def roundtrip_verify(apk_path: Path, work_dir: Path) -> dict[str, Any]:
    """Losslessly decode/build an APK and report all semantic differences."""
    apk_path, work_dir = Path(apk_path), Path(work_dir)
    project = work_dir / "project"
    rebuilt = work_dir / "rebuilt.apk"
    if project.exists():
        shutil.rmtree(project)
    decode_apk(apk_path, project, backend="raw")
    build_project(project, rebuilt)
    result = diff_apks(apk_path, rebuilt)
    result["rebuilt_apk"] = str(rebuilt)
    result["valid"] = verify_apk(rebuilt)["valid"]
    result["verdict"] = (
        "PASS"
        if not result["files"]["added"]
        and not result["files"]["removed"]
        and not result["files"]["changed"]
        and not any(result["dex"][key] for key in result["dex"])
        else "DIFFERENT"
    )
    # ZIP metadata and compression can change while entry bytes remain equal.
    if result["files"]["added"] == result["files"]["removed"] == result["files"]["changed"] == []:
        result["verdict"] = "PASS"
    return result


def framework_check(apk_path: Path) -> dict[str, Any]:
    info = inspect_apk(apk_path)
    target = info.get("manifest", {}).get("target_sdk", "")
    tool = _apktool_command()
    return {
        "apk": str(apk_path),
        "target_sdk": target,
        "apktool_available": tool is not None,
        "verdict": "READY" if tool else "RAW_BACKEND_ONLY",
        "message": (
            "apktool is available for compiled-resource rebuilds"
            if tool
            else "APEX can analyze and losslessly repack raw files; install apktool "
            "or set APEX_APKTOOL_JAR to rebuild edited XML/resources"
        ),
    }


def doctor() -> dict[str, Any]:
    tools = {
        "java": _command_path("java"),
        "apktool": (_apktool_command() or [None])[0],
        "apksigner": _command_path("apksigner", "APEX_APKSIGNER"),
        "adb": _command_path("adb", "APEX_ADB"),
        "aapt2": _command_path("aapt2", "APEX_AAPT2"),
    }
    try:
        import androguard

        androguard_version = getattr(androguard, "__version__", "installed")
    except ImportError:
        androguard_version = None
    from .device_profile import doctor_fields

    return {
        "apex": __version__,
        "edition": __import__("apex.edition", fromlist=["edition_info"]).edition_info(),
        "androguard": androguard_version,
        "native_zip": __import__("apex.analysis", fromlist=["_native_zip"])._native_zip is not None,
        "native_dex": __import__("apex.analysis", fromlist=["_native_dex"])._native_dex is not None,
        "tools": tools,
        "ready": androguard_version is not None,
        **doctor_fields(),
    }
