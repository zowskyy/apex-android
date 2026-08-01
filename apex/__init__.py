from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


ENTRY_POINT_HINTS = ("MainActivity", "Application", "Service", "Receiver", "Provider")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_ZIP_TRAVERSAL_MAX_NAME_LEN = 4096


def _fallback_sanitized_name(raw_name: str) -> str | None:
    """Pure-Python mirror of core/zip_reader/src/sanitize.rs::check_name.

    Only used when the apex_zip_reader native extension isn't installed —
    keeps extract_apk() safe against CVE-2026-39973-style traversal even
    without the compiled Rust module. Returns None if the entry must be
    refused outright.
    """
    if not raw_name or len(raw_name) > _ZIP_TRAVERSAL_MAX_NAME_LEN or "\0" in raw_name:
        return None
    normalized = raw_name.replace("\\", "/")
    if normalized.startswith("/"):
        return None
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        return None
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts) or not parts:
        return None
    return "/".join(parts)


def _fallback_extract_apk(apk_path: Path, extract_dir: Path) -> dict[str, Any]:
    extracted = 0
    warned = 0
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path, "r") as zf:
        for info in zf.infolist():
            safe_name = _fallback_sanitized_name(info.filename)
            if safe_name is None:
                warned += 1
                entries.append({"name": info.filename, "verdict": "WARN", "reason": "path-traversal/absolute/oversized name"})
                continue
            dest = (extract_dir / safe_name).resolve()
            if not str(dest).startswith(str(extract_dir.resolve())):
                warned += 1
                entries.append({"name": info.filename, "verdict": "WARN", "reason": "resolved path escapes destination root"})
                continue
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, dest.open("wb") as out:
                    shutil.copyfileobj(src, out)
            extracted += 1
            entries.append({"name": info.filename, "verdict": "CLEAN"})
    return {"total_entries": len(entries), "extracted": extracted, "warned": warned, "entries": entries, "backend": "python-fallback"}


def extract_apk(apk_path: Path, work_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Extract an APK/ZIP with path-traversal sanitization on every entry.

    Returns (extract_dir, security_report). WARN entries in the report were
    refused, not extracted — callers should surface them, not silently drop them.
    """
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        import apex_zip_reader as _native_zip
    except Exception:
        _native_zip = None
    if _native_zip is not None:
        report = _native_zip.extract_apk(str(apk_path), str(extract_dir))
        report = dict(report)
        report["backend"] = "rust"
    else:
        report = _fallback_extract_apk(apk_path, extract_dir)
    return extract_dir, report


def inventory_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def xml_info(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
        return {"tag": root.tag, "attrib": root.attrib}
    except Exception as e:
        return {"error": repr(e)}


def scan_resources(extract_dir: Path) -> dict[str, Any]:
    manifest = extract_dir / "AndroidManifest.xml"
    res_dir = extract_dir / "res"
    assets_dir = extract_dir / "assets"
    arsc = extract_dir / "resources.arsc"

    return {
        "manifest_present": manifest.exists(),
        "resources_arsc_present": arsc.exists(),
        "manifest_xml": xml_info(manifest) if manifest.exists() else {},
        "res_files": inventory_files(res_dir) if res_dir.exists() else [],
        "asset_files": inventory_files(assets_dir) if assets_dir.exists() else [],
    }


def scan_native_libs(extract_dir: Path, keep_abi: list[str] | None = None) -> dict[str, Any]:
    lib_dir = extract_dir / "lib"
    items = []
    if lib_dir.exists():
        for abi_dir in sorted(p for p in lib_dir.iterdir() if p.is_dir()):
            if keep_abi and abi_dir.name not in keep_abi:
                continue
            for so in sorted(abi_dir.rglob("*.so")):
                items.append({
                    "abi": abi_dir.name,
                    "path": so.relative_to(extract_dir).as_posix(),
                    "size": so.stat().st_size,
                    "sha256": sha256_file(so),
                })
    return {"native_libs": items}


def scan_dex_metadata(extract_dir: Path) -> dict[str, Any]:
    dex_files = sorted(extract_dir.glob("classes*.dex"))
    classes = []
    methods = []
    strings = []
    edges = []

    for dex in dex_files:
        classes.append({"dex": dex.name, "name": dex.stem, "note": "DEX parser backend not configured"})
        methods.append({"class": dex.stem, "name": "<unknown>"})
    return {
        "dex_files": [p.name for p in dex_files],
        "classes": classes,
        "methods": methods,
        "strings": strings,
        "edges": edges,
    }


def build_crossrefs(dex_index: dict[str, Any]) -> dict[str, Any]:
    graph = {"nodes": [], "edges": []}
    for c in dex_index.get("classes", []):
        if c.get("name"):
            graph["nodes"].append({"id": c["name"], "kind": "class"})
    for m in dex_index.get("methods", []):
        if m.get("class") and m.get("name"):
            mid = f"{m['class']}::{m['name']}"
            graph["nodes"].append({"id": mid, "kind": "method"})
            graph["edges"].append({"src": m["class"], "dst": mid})
    for e in dex_index.get("edges", []):
        caller = f"{e.get('caller_class')}::{e.get('caller_method')}"
        callee = e.get("callee")
        if caller and callee:
            graph["edges"].append({"src": caller, "dst": callee})
    return graph


def build_reachability(dex_index: dict[str, Any], resource_index: dict[str, Any], native_index: dict[str, Any]) -> dict[str, Any]:
    classes = dex_index.get("classes", [])
    methods = dex_index.get("methods", [])
    entry_points = [c["name"] for c in classes if any(h.lower() in c.get("name", "").lower() for h in ENTRY_POINT_HINTS)]

    reachable_nodes = set()
    reachable_nodes.update(entry_points)

    return {
        "entry_points": entry_points,
        "reachable_nodes": sorted(reachable_nodes),
        "class_count": len(classes),
        "method_count": len(methods),
        "edge_count": len(dex_index.get("edges", [])),
        "native_count": len(native_index.get("native_libs", [])),
        "resource_count": len(resource_index.get("res_files", [])),
    }


def export_minimal_bundle(extract_dir: Path, out_dir: Path, keep_abi: list[str] | None = None) -> dict[str, Any]:
    export_dir = out_dir / "bundle"
    export_dir.mkdir(parents=True, exist_ok=True)
    kept = []

    for rel in ["AndroidManifest.xml", "resources.arsc"]:
        src = extract_dir / rel
        if src.exists():
            shutil.copy2(src, export_dir / src.name)
            kept.append(rel)

    for folder in ["res", "assets"]:
        src = extract_dir / folder
        if src.exists():
            shutil.copytree(src, export_dir / folder, dirs_exist_ok=True)
            kept.append(folder)

    lib_src = extract_dir / "lib"
    if lib_src.exists():
        for abi_dir in sorted(p for p in lib_src.iterdir() if p.is_dir()):
            if keep_abi and abi_dir.name not in keep_abi:
                continue
            shutil.copytree(abi_dir, export_dir / "lib" / abi_dir.name, dirs_exist_ok=True)
            kept.append(f"lib/{abi_dir.name}")

    for dex in sorted(extract_dir.glob("classes*.dex")):
        shutil.copy2(dex, export_dir / dex.name)
        kept.append(dex.name)

    data = {"export_dir": str(export_dir), "kept": kept}
    (out_dir / "export_index.json").write_text(json.dumps(data, indent=2))
    return data


def diff_indexes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_classes = {x.get("name") for x in left.get("classes", []) if x.get("name")}
    right_classes = {x.get("name") for x in right.get("classes", []) if x.get("name")}

    left_methods = {f"{x.get('class')}::{x.get('name')}" for x in left.get("methods", []) if x.get("class") and x.get("name")}
    right_methods = {f"{x.get('class')}::{x.get('name')}" for x in right.get("methods", []) if x.get("class") and x.get("name")}

    return {
        "classes_added": sorted(right_classes - left_classes),
        "classes_removed": sorted(left_classes - right_classes),
        "methods_added": sorted(right_methods - left_methods),
        "methods_removed": sorted(left_methods - right_methods),
        "dex_files_added": sorted(set(right.get("dex_files", [])) - set(left.get("dex_files", []))),
        "dex_files_removed": sorted(set(left.get("dex_files", [])) - set(right.get("dex_files", []))),
    }


class Store:
    def put(self, name: str, data: dict[str, Any]) -> None:
        raise NotImplementedError


class SQLiteStore(Store):
    def __init__(self, path: Path):
        import sqlite3

        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS kv (name TEXT PRIMARY KEY, json TEXT NOT NULL)")
        self.conn.commit()

    def put(self, name: str, data: dict[str, Any]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO kv(name, json) VALUES (?, ?)", (name, json.dumps(data)))
        self.conn.commit()


class PostgresStore(Store):
    def __init__(self, dsn: str):
        import psycopg
        self.conn = psycopg.connect(dsn)
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS kv (name TEXT PRIMARY KEY, json JSONB NOT NULL)")
        self.conn.commit()

    def put(self, name: str, data: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO kv(name, json) VALUES (%s, %s) ON CONFLICT (name) DO UPDATE SET json = EXCLUDED.json",
                        (name, json.dumps(data)))
        self.conn.commit()


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>APK Analysis Report</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; background: #0d1117; color: #c9d1d9; }
    h1, h2, h3 { color: #58a6ff; }
    code, pre { background: #161b22; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.9em; }
    pre { padding: 1rem; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    td, th { border: 1px solid #30363d; padding: 0.5rem 0.75rem; text-align: left; }
    th { background: #161b22; color: #58a6ff; }
    tr:nth-child(even) { background: #161b22; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8em; font-weight: bold; }
    .pass { background: #238636; color: #fff; }
    .warn { background: #9e6a03; color: #fff; }
    .fail { background: #da3633; color: #fff; }
    .section { border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }
  </style>
</head>
<body>
  <h1>APEX — APK Analysis Report</h1>
  <div class="section">
    <h2>Overview</h2>
    <table>
      <tr><th>APK</th><td>{{ meta.apk_path }}</td></tr>
      <tr><th>SHA-256</th><td><code>{{ meta.sha256 }}</code></td></tr>
      <tr><th>Size</th><td>{{ meta.size_bytes }} bytes</td></tr>
      <tr><th>DEX files</th><td>{{ dex.dex_files | join(', ') }}</td></tr>
      <tr><th>Native ABIs</th><td>{{ native.native_libs | map(attribute='abi') | unique | join(', ') or 'none' }}</td></tr>
      <tr><th>Classes (stub)</th><td>{{ reach.class_count }}</td></tr>
      <tr><th>Methods (stub)</th><td>{{ reach.method_count }}</td></tr>
      <tr><th>Resources</th><td>{{ reach.resource_count }}</td></tr>
    </table>
  </div>

  <div class="section">
    <h2>Entry Points</h2>
    {% if reach.entry_points %}
    <ul>{% for ep in reach.entry_points %}<li><code>{{ ep }}</code></li>{% endfor %}</ul>
    {% else %}
    <p>No well-known Android entry-point classes detected in stub index.</p>
    {% endif %}
  </div>

  <div class="section">
    <h2>Native Libraries</h2>
    {% if native.native_libs %}
    <table>
      <tr><th>ABI</th><th>Path</th><th>Size</th><th>SHA-256</th></tr>
      {% for lib in native.native_libs %}
      <tr>
        <td>{{ lib.abi }}</td>
        <td><code>{{ lib.path }}</code></td>
        <td>{{ lib.size }}</td>
        <td><code>{{ lib.sha256[:16] }}…</code></td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p>No native libraries found.</p>
    {% endif %}
  </div>

  <div class="section">
    <h2>Resources</h2>
    <p>Manifest present: <span class="badge {{ 'pass' if resources.manifest_present else 'fail' }}">{{ resources.manifest_present }}</span></p>
    <p>resources.arsc present: <span class="badge {{ 'pass' if resources.resources_arsc_present else 'fail' }}">{{ resources.resources_arsc_present }}</span></p>
    <p>res/ file count: {{ resources.res_files | length }}</p>
    <p>assets/ file count: {{ resources.asset_files | length }}</p>
  </div>

  <div class="section">
    <h2>Cross-Reference Graph (stub)</h2>
    <p>Nodes: {{ xref.nodes | length }} &nbsp;|&nbsp; Edges: {{ xref.edges | length }}</p>
    <p><em>Full DEX parser backend not yet wired — graph shows class/method stubs only.</em></p>
  </div>
</body>
</html>"""


def render_html(meta: dict, dex: dict, native: dict, resources: dict, reach: dict, xref: dict) -> str:
    try:
        from jinja2 import Template
    except Exception:
        Template = None
    if Template is None:
        return f"<pre>Jinja2 not installed.\n{json.dumps({'meta': meta, 'reach': reach}, indent=2)}</pre>"
    t = Template(HTML_TEMPLATE)
    return t.render(meta=meta, dex=dex, native=native, resources=resources, reach=reach, xref=xref)


def analyze(apk_path: Path, out_dir: Path, keep_abi: list[str] | None = None, store: Store | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "work"

    meta = {
        "apk_path": str(apk_path),
        "sha256": sha256_file(apk_path),
        "size_bytes": apk_path.stat().st_size,
    }

    extract_dir, zip_security = extract_apk(apk_path, work_dir)
    resources = scan_resources(extract_dir)
    native = scan_native_libs(extract_dir, keep_abi)
    dex = scan_dex_metadata(extract_dir)
    xref = build_crossrefs(dex)
    reach = build_reachability(dex, resources, native)
    bundle = export_minimal_bundle(extract_dir, out_dir, keep_abi)

    report = {
        "meta": meta,
        "security": {
            "zip_extraction": {
                "backend": zip_security.get("backend"),
                "total_entries": zip_security.get("total_entries"),
                "extracted": zip_security.get("extracted"),
                "warned": zip_security.get("warned"),
                "warnings": [e for e in zip_security.get("entries", []) if e.get("verdict") == "WARN"],
            }
        },
        "resources": resources,
        "native": native,
        "dex": dex,
        "crossrefs": xref,
        "reachability": reach,
        "bundle": bundle,
    }

    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    html = render_html(meta, dex, native, resources, reach, xref)
    (out_dir / "report.html").write_text(html, encoding="utf-8")

    if store:
        store.put("meta", meta)
        store.put("resources", resources)
        store.put("native", native)
        store.put("dex", dex)
        store.put("reachability", reach)

    return report


def cmd_analyze(args: argparse.Namespace) -> None:
    apk = Path(args.apk)
    if not apk.exists():
        print(f"error: {apk} not found", file=sys.stderr)
        sys.exit(1)
    out = Path(args.out)
    keep_abi = args.abi.split(",") if args.abi else None

    store: Store | None = None
    if args.db:
        store = SQLiteStore(Path(args.db))
    elif args.pg:
        store = PostgresStore(args.pg)

    report = analyze(apk, out, keep_abi, store)
    print(f"report.json  -> {out}/report.json")
    print(f"report.html  -> {out}/report.html")
    print(f"bundle/      -> {out}/bundle/")
    print(f"classes: {report['reachability']['class_count']}  methods: {report['reachability']['method_count']}")


def cmd_diff(args: argparse.Namespace) -> None:
    left_report = json.loads(Path(args.left).read_text())
    right_report = json.loads(Path(args.right).read_text())
    result = diff_indexes(left_report.get("dex", {}), right_report.get("dex", {}))
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="apex", description="APEX — Android Package EXaminer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    from .commands import add_cli_commands

    add_cli_commands(sub)

    a = sub.add_parser("analyze", help="Full APK analysis")
    a.add_argument("apk")
    a.add_argument("--out", default="apex_out", help="Output directory")
    a.add_argument("--abi", default="", help="Comma-separated ABI filter (e.g. arm64-v8a,x86_64)")
    a.add_argument("--db", default="", help="SQLite path for persistent store")
    a.add_argument("--pg", default="", help="PostgreSQL DSN for persistent store")
    a.set_defaults(func=cmd_analyze)

    d = sub.add_parser("diff", help="Diff two report.json files")
    d.add_argument("left")
    d.add_argument("right")
    d.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
