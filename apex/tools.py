"""Shared APEX tool registry used by MCP, Code Pilot, and automation.

Every tool is a single callable so CLI, web, MCP, and the agent stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .analysis import inspect_apk
from .workflows import (
    analyze_apk,
    decode_apk,
    decompile_apk,
    diff_apks,
    doctor,
    framework_check,
    roundtrip_verify,
    security_scan,
    verify_apk,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., dict[str, Any]]
    parameters: dict[str, Any]


def _tool_inspect(path: str, include_files: bool = False) -> dict[str, Any]:
    return inspect_apk(Path(path), include_files=include_files)


def _tool_security_scan(path: str) -> dict[str, Any]:
    return security_scan(Path(path))


def _tool_analyze(path: str, out_dir: str = "apex_out") -> dict[str, Any]:
    report = analyze_apk(Path(path), Path(out_dir))
    return {
        "report_json": str(Path(out_dir) / "report.json"),
        "report_html": str(Path(out_dir) / "report.html"),
        "class_count": report["reachability"]["class_count"],
        "method_count": report["reachability"]["method_count"],
        "package": report["resources"].get("manifest", {}).get("package"),
    }


def _tool_decompile(path: str, out_dir: str = "apex_decompiled") -> dict[str, Any]:
    result = decompile_apk(Path(path), Path(out_dir))
    return {
        "out_dir": out_dir,
        "class_count": len(result["classes"]),
        "dex_files": result["dex_files"],
        "errors": result["errors"],
    }


def _tool_decode(path: str, out_dir: str = "apex_decoded", backend: str = "auto") -> dict[str, Any]:
    return decode_apk(Path(path), Path(out_dir), backend)


def _tool_verify(path: str) -> dict[str, Any]:
    return verify_apk(Path(path))


def _tool_diff(left: str, right: str) -> dict[str, Any]:
    return diff_apks(Path(left), Path(right))


def _tool_roundtrip(path: str, work_dir: str = "apex_roundtrip") -> dict[str, Any]:
    return roundtrip_verify(Path(path), Path(work_dir))


def _tool_framework_check(path: str) -> dict[str, Any]:
    return framework_check(Path(path))


def _tool_doctor() -> dict[str, Any]:
    from .edition import edition_info

    return {**doctor(), "edition": edition_info()}


TOOL_SPECS: dict[str, ToolSpec] = {
    "doctor": ToolSpec(
        "doctor",
        "Report APEX engine health, installed tools, and active edition.",
        _tool_doctor,
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "inspect": ToolSpec(
        "inspect",
        "Fast APK metadata inspection: manifest, DEX inventory, native ABIs, resources.",
        _tool_inspect,
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "include_files": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    ),
    "security_scan": ToolSpec(
        "security_scan",
        "Static security scan: ZIP traversal, zip-bomb signals, manifest flags, ARSC paths.",
        _tool_security_scan,
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ),
    "analyze": ToolSpec(
        "analyze",
        "Full analysis report with DEX crossrefs, reachability, and HTML output.",
        _tool_analyze,
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "out_dir": {"type": "string", "default": "apex_out"},
            },
            "required": ["path"],
        },
    ),
    "decompile": ToolSpec(
        "decompile",
        "Decompile DEX bytecode to Java source and readable Dalvik smali.",
        _tool_decompile,
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "out_dir": {"type": "string", "default": "apex_decompiled"},
            },
            "required": ["path"],
        },
    ),
    "decode": ToolSpec(
        "decode",
        "Decode APK to an editable project (raw lossless or apktool backend).",
        _tool_decode,
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "out_dir": {"type": "string", "default": "apex_decoded"},
                "backend": {"type": "string", "enum": ["auto", "raw", "apktool"], "default": "auto"},
            },
            "required": ["path"],
        },
    ),
    "verify": ToolSpec(
        "verify",
        "Validate APK structure, DEX integrity, and signature metadata.",
        _tool_verify,
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ),
    "diff": ToolSpec(
        "diff",
        "Semantic diff of two APK files (files + DEX classes/methods).",
        _tool_diff,
        {
            "type": "object",
            "properties": {"left": {"type": "string"}, "right": {"type": "string"}},
            "required": ["left", "right"],
        },
    ),
    "roundtrip": ToolSpec(
        "roundtrip",
        "Losslessly decode/build an APK and report semantic differences.",
        _tool_roundtrip,
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "work_dir": {"type": "string", "default": "apex_roundtrip"},
            },
            "required": ["path"],
        },
    ),
    "framework_check": ToolSpec(
        "framework_check",
        "Check whether compiled-resource rebuild support (apktool) is available.",
        _tool_framework_check,
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ),
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        }
        for spec in TOOL_SPECS.values()
    ]


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in TOOL_SPECS:
        raise KeyError(f"unknown tool: {name}")
    return TOOL_SPECS[name].handler(**(arguments or {}))


def tool_catalog_for_prompt() -> str:
    lines = []
    for spec in TOOL_SPECS.values():
        required = spec.parameters.get("required", [])
        props = ", ".join(
            f"{key}{'*' if key in required else ''}"
            for key in spec.parameters.get("properties", {})
        )
        lines.append(f"- {spec.name}({props}): {spec.description}")
    return "\n".join(lines)
