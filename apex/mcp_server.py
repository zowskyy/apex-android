"""MCP server exposing APEX reverse-engineering tools to AI assistants.

Requires the Pro edition. Connect from Cursor, Claude Desktop, or any MCP host:

```json
{
  "mcpServers": {
    "apex": {
      "command": "apex",
      "args": ["mcp"]
    }
  }
}
```

Or with an explicit license key:

```json
{
  "mcpServers": {
    "apex": {
      "command": "apex",
      "args": ["mcp"],
      "env": {
        "APEX_LICENSE_KEY": "APEX-PRO-...",
        "APEX_ENTITLEMENT": "your-customer-id"
      }
    }
  }
}
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .edition import EditionError, Feature, edition_info, require_feature


def run_mcp_server() -> None:
    """Start the stdio MCP server (Pro edition)."""
    require_feature(Feature.MCP_SERVER)
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise EditionError(
            "MCP server requires the optional 'fastmcp' package. "
            "Install with: pip install apex-android[mcp]"
        ) from exc

    from .analysis import inspect_apk as inspect_apk_fn
    from .workflows import (
        analyze_apk,
        decode_apk,
        decompile_apk,
        diff_apks,
        doctor,
        security_scan,
        verify_apk,
    )

    mcp = FastMCP(
        "apex-android",
        instructions=(
            "APEX inspects, decompiles, decodes, and security-scans Android APK files. "
            "All paths must be absolute local filesystem paths."
        ),
    )

    @mcp.tool()
    def apex_doctor() -> dict[str, Any]:
        """Report APEX engine health, installed tools, and active edition."""
        return {**doctor(), "edition": edition_info()}

    @mcp.tool()
    def apex_inspect(path: str, include_files: bool = False) -> dict[str, Any]:
        """Fast APK metadata inspection: manifest, DEX inventory, native ABIs, resources."""
        return inspect_apk_fn(Path(path), include_files=include_files)

    @mcp.tool()
    def apex_security_scan(path: str) -> dict[str, Any]:
        """Static security scan: ZIP traversal, zip-bom signals, manifest flags, ARSC paths."""
        return security_scan(Path(path))

    @mcp.tool()
    def apex_analyze(path: str, out_dir: str = "apex_out") -> dict[str, Any]:
        """Full analysis report with DEX crossrefs, reachability, and HTML output."""
        report = analyze_apk(Path(path), Path(out_dir))
        return {
            "report_json": str(Path(out_dir) / "report.json"),
            "report_html": str(Path(out_dir) / "report.html"),
            "class_count": report["reachability"]["class_count"],
            "method_count": report["reachability"]["method_count"],
            "package": report["resources"].get("manifest", {}).get("package"),
        }

    @mcp.tool()
    def apex_decompile(path: str, out_dir: str = "apex_decompiled") -> dict[str, Any]:
        """Decompile DEX bytecode to Java source and readable Dalvik smali."""
        result = decompile_apk(Path(path), Path(out_dir))
        return {
            "out_dir": out_dir,
            "class_count": len(result["classes"]),
            "dex_files": result["dex_files"],
            "errors": result["errors"],
        }

    @mcp.tool()
    def apex_decode(path: str, out_dir: str = "apex_decoded", backend: str = "auto") -> dict[str, Any]:
        """Decode APK to an editable project (raw lossless or apktool backend)."""
        return decode_apk(Path(path), Path(out_dir), backend)

    @mcp.tool()
    def apex_verify(path: str) -> dict[str, Any]:
        """Validate APK structure, DEX integrity, and signature metadata."""
        return verify_apk(Path(path))

    @mcp.tool()
    def apex_diff(left: str, right: str) -> dict[str, Any]:
        """Semantic diff of two APK files (files + DEX classes/methods)."""
        return diff_apks(Path(left), Path(right))

    mcp.run(transport="stdio")
