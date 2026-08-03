"""MCP server exposing APEX reverse-engineering tools to AI assistants.

Requires the Pro edition. Tools share the `apex.tools` registry with Code Pilot.
"""

from __future__ import annotations

from typing import Any

from .edition import EditionError, Feature, require_feature
from .tools import call_tool


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
        return call_tool("doctor")

    @mcp.tool()
    def apex_inspect(path: str, include_files: bool = False) -> dict[str, Any]:
        """Fast APK metadata inspection: manifest, DEX inventory, native ABIs, resources."""
        return call_tool("inspect", {"path": path, "include_files": include_files})

    @mcp.tool()
    def apex_security_scan(path: str) -> dict[str, Any]:
        """Static security scan: ZIP traversal, zip-bomb signals, manifest flags, ARSC paths."""
        return call_tool("security_scan", {"path": path})

    @mcp.tool()
    def apex_analyze(path: str, out_dir: str = "apex_out") -> dict[str, Any]:
        """Full analysis report with DEX crossrefs, reachability, and HTML output."""
        return call_tool("analyze", {"path": path, "out_dir": out_dir})

    @mcp.tool()
    def apex_decompile(path: str, out_dir: str = "apex_decompiled") -> dict[str, Any]:
        """Decompile DEX bytecode to Java source and readable Dalvik smali."""
        return call_tool("decompile", {"path": path, "out_dir": out_dir})

    @mcp.tool()
    def apex_decode(path: str, out_dir: str = "apex_decoded", backend: str = "auto") -> dict[str, Any]:
        """Decode APK to an editable project (raw lossless or apktool backend)."""
        return call_tool("decode", {"path": path, "out_dir": out_dir, "backend": backend})

    @mcp.tool()
    def apex_verify(path: str) -> dict[str, Any]:
        """Validate APK structure, DEX integrity, and signature metadata."""
        return call_tool("verify", {"path": path})

    @mcp.tool()
    def apex_diff(left: str, right: str) -> dict[str, Any]:
        """Semantic diff of two APK files (files + DEX classes/methods)."""
        return call_tool("diff", {"left": left, "right": right})

    @mcp.tool()
    def apex_roundtrip(path: str, work_dir: str = "apex_roundtrip") -> dict[str, Any]:
        """Losslessly decode/build an APK and report semantic differences."""
        return call_tool("roundtrip", {"path": path, "work_dir": work_dir})

    @mcp.tool()
    def apex_framework_check(path: str) -> dict[str, Any]:
        """Check whether compiled-resource rebuild support (apktool) is available."""
        return call_tool("framework_check", {"path": path})

    mcp.run(transport="stdio")
