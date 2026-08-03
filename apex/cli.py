"""Command-line interface for APEX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analysis import ApexError, diff_indexes, inspect_apk
from .disclaimer import require_disclaimer_acceptance
from .edition import EditionError, Feature, require_feature
from .version import __version__
from .web import serve
from .workflows import (
    PostgresStore,
    SQLiteStore,
    analyze_apk,
    build_project,
    decode_apk,
    decompile_apk,
    diff_apks,
    doctor,
    framework_check,
    roundtrip_verify,
    security_scan,
    verify_apk,
)

VERSION = __version__


def _print(data: Any, output: str | None = None) -> None:
    text = json.dumps(data, indent=2, default=str)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(output)
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apex",
        description="APEX — secure Android package inspection, decompilation, and rebuilding",
    )
    parser.add_argument("--version", action="version", version=f"APEX {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = sub.add_parser("inspect", help="fast APK metadata inspection")
    inspect_cmd.add_argument("apk")
    inspect_cmd.add_argument("--files", action="store_true", help="include complete file inventory")
    inspect_cmd.add_argument("--output", "-o", help="write JSON to a file")

    analyze_cmd = sub.add_parser("analyze", help="create a complete JSON and HTML analysis report")
    analyze_cmd.add_argument("apk")
    analyze_cmd.add_argument("--out", default="apex_out")
    analyze_cmd.add_argument("--abi", default="", help="comma-separated ABI allowlist")
    analyze_cmd.add_argument("--db", help="store report sections in SQLite")
    analyze_cmd.add_argument("--pg", help="store report sections in PostgreSQL")

    decompile_cmd = sub.add_parser("decompile", help="decompile DEX to Java and readable Dalvik")
    decompile_cmd.add_argument("apk")
    decompile_cmd.add_argument("--out", default="apex_decompiled")
    decompile_cmd.add_argument("--mapping", help="ProGuard/R8 mapping.txt")
    decompile_cmd.add_argument("--no-smali", action="store_true")

    decode_cmd = sub.add_parser("decode", help="decode APK to an editable project")
    decode_cmd.add_argument("apk")
    decode_cmd.add_argument("--out", default="apex_decoded")
    decode_cmd.add_argument("--backend", choices=["auto", "raw", "apktool"], default="auto")

    build_cmd = sub.add_parser("build", help="build an APK from an APEX project")
    build_cmd.add_argument("project")
    build_cmd.add_argument("--out", default="apex-built.apk")
    build_cmd.add_argument("--keystore")
    build_cmd.add_argument("--alias", default="androiddebugkey")
    build_cmd.add_argument("--storepass", default="android")
    build_cmd.add_argument("--keypass")

    verify_cmd = sub.add_parser("verify", help="validate APK structure, DEX files, and signatures")
    verify_cmd.add_argument("apk")
    verify_cmd.add_argument("--output", "-o")

    roundtrip_cmd = sub.add_parser("roundtrip", help="decode, rebuild, and compare an APK")
    roundtrip_cmd.add_argument("apk")
    roundtrip_cmd.add_argument("--work", default="apex_roundtrip")
    roundtrip_cmd.add_argument("--output", "-o")

    security_cmd = sub.add_parser(
        "security-scan", help="scan archive and manifest security signals"
    )
    security_cmd.add_argument("apk")
    security_cmd.add_argument("--output", "-o")

    diff_cmd = sub.add_parser("diff", help="semantic APK or report diff")
    diff_cmd.add_argument("left")
    diff_cmd.add_argument("right")
    diff_cmd.add_argument("--output", "-o")

    framework_cmd = sub.add_parser(
        "framework-check", help="check whether compiled-resource rebuild support is available"
    )
    framework_cmd.add_argument("apk")

    gate_cmd = sub.add_parser(
        "gate",
        help="run static hard-gate checks (manifest MSV, DEX, security) for CI",
    )
    gate_cmd.add_argument("apk")
    gate_cmd.add_argument("--msv", type=int, default=28, help="minimum supported SDK (default 28)")
    gate_cmd.add_argument(
        "--stage",
        choices=["candidate", "rc", "beta", "production"],
        default="candidate",
        help="promotion stage thresholds (Slice 7)",
    )
    gate_cmd.add_argument("--out", "-o", default="gate.json", help="write gate.json report")
    gate_cmd.add_argument(
        "--ci",
        action="store_true",
        help="exit 1 if gate_passed is false (for pipelines)",
    )

    sub.add_parser("doctor", help="show parser and external tool availability")

    gui_cmd = sub.add_parser("gui", aliases=["serve"], help="start the local web interface")
    gui_cmd.add_argument("--host", default="127.0.0.1")
    gui_cmd.add_argument("--port", type=int, default=8765)
    gui_cmd.add_argument("--workspace", default=".apex-web")
    gui_cmd.add_argument("--no-browser", action="store_true")
    gui_cmd.add_argument(
        "--mobile",
        action="store_true",
        help="listen on all interfaces for phone browser access (same Wi-Fi)",
    )

    mobile_cmd = sub.add_parser(
        "mobile",
        help="companion mode: web UI on LAN for the thin phone client (analysis on this PC)",
    )
    mobile_cmd.add_argument("--port", type=int, default=8765)
    mobile_cmd.add_argument("--workspace", default=".apex-web")

    standalone_cmd = sub.add_parser(
        "standalone",
        help="on-device engine mode (localhost only, adaptive limits — used inside the phone APK)",
    )
    standalone_cmd.add_argument("--port", type=int, default=8765)
    standalone_cmd.add_argument("--workspace", default=".apex-standalone")
    standalone_cmd.add_argument("--ram-mb", type=int, default=0, help="simulate device RAM for tier testing")
    standalone_cmd.add_argument(
        "--remote-enhanced",
        action="store_true",
        help="use remote-server limits profile (desktop connected as backend)",
    )

    wrapper_cmd = sub.add_parser("wrapper", help="list or install platform app wrappers")
    wrapper_cmd.add_argument(
        "action",
        nargs="?",
        choices=["list", "install"],
        default="list",
        help="list available wrappers or run platform installer",
    )

    mcp_cmd = sub.add_parser("mcp", help="start the MCP server for AI assistant integration (Pro)")
    mcp_cmd.add_argument(
        "license_action",
        nargs="?",
        choices=["show-key"],
        help="show-key: print the evaluation Pro license key",
    )

    agent_cmd = sub.add_parser(
        "agent",
        aliases=["codepilot", "pilot"],
        help="APEX Code Pilot — prompt-driven reverse engineering assistant (Pro)",
    )
    agent_cmd.add_argument("prompt", nargs="?", help="what you want to do")
    agent_cmd.add_argument("--apk", help="active APK path for this session")
    agent_cmd.add_argument(
        "--provider",
        default=None,
        help="openai | ollama | heuristic (default: APEX_AGENT_PROVIDER or openai)",
    )
    agent_cmd.add_argument(
        "--playbook",
        choices=["triage", "decompile", "rebuild", "compare"],
        help="optional guided playbook",
    )
    agent_cmd.add_argument("--trace", action="store_true", help="include tool call trace in output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            _print(inspect_apk(Path(args.apk), include_files=args.files), args.output)
        elif args.command == "analyze":
            store = None
            if args.db:
                store = SQLiteStore(Path(args.db))
            elif args.pg:
                require_feature(Feature.POSTGRES_STORE)
                store = PostgresStore(args.pg)
            abi = [item for item in args.abi.split(",") if item] or None
            report = analyze_apk(Path(args.apk), Path(args.out), abi, store)
            print(f"JSON report: {Path(args.out) / 'report.json'}")
            print(f"HTML report: {Path(args.out) / 'report.html'}")
            print(
                f"Classes: {report['reachability']['class_count']} · "
                f"Methods: {report['reachability']['method_count']}"
            )
        elif args.command == "decompile":
            result = decompile_apk(
                Path(args.apk),
                Path(args.out),
                Path(args.mapping) if args.mapping else None,
                not args.no_smali,
            )
            print(f"Decompiled {len(result['classes'])} classes to {args.out}")
            if result["errors"]:
                print(f"Warnings: {len(result['errors'])}", file=sys.stderr)
        elif args.command == "decode":
            result = decode_apk(Path(args.apk), Path(args.out), args.backend)
            print(f"Decoded with {result['backend']} backend to {args.out}")
        elif args.command == "build":
            result = build_project(
                Path(args.project),
                Path(args.out),
                sign_keystore=Path(args.keystore) if args.keystore else None,
                sign_alias=args.alias,
                storepass=args.storepass,
                keypass=args.keypass,
            )
            _print(result)
        elif args.command == "verify":
            result = verify_apk(Path(args.apk))
            _print(result, args.output)
            return 0 if result["valid"] else 2
        elif args.command == "roundtrip":
            result = roundtrip_verify(Path(args.apk), Path(args.work))
            _print(result, args.output)
            return 0 if result["verdict"] == "PASS" else 3
        elif args.command == "security-scan":
            result = security_scan(Path(args.apk))
            _print(result, args.output)
            return 0 if result["verdict"] in {"CLEAN", "REVIEW"} else 4
        elif args.command == "diff":
            left, right = Path(args.left), Path(args.right)
            if left.suffix.lower() == right.suffix.lower() == ".json":
                left_data = json.loads(left.read_text(encoding="utf-8")).get("dex", {})
                right_data = json.loads(right.read_text(encoding="utf-8")).get("dex", {})
                result = diff_indexes(left_data, right_data)
            else:
                result = diff_apks(left, right)
            _print(result, args.output)
        elif args.command == "framework-check":
            _print(framework_check(Path(args.apk)))
        elif args.command == "gate":
            from .gate import run_hard_gate, write_gate_report

            report = run_hard_gate(
                Path(args.apk),
                msv=int(args.msv),
                stage=args.stage,
            )
            out = write_gate_report(report, Path(args.out))
            print(f"Gate report: {out}")
            print(
                f"score={report.score:.1f} stage={report.stage} "
                f"passed={report.gate_passed} blocking={len(report.blocking)}"
            )
            if args.ci and not report.gate_passed:
                for issue in report.blocking:
                    print(f"BLOCK: {issue}", file=sys.stderr)
                return 5
            return 0
        elif args.command == "doctor":
            _print(doctor())
        elif args.command in {"gui", "serve"}:
            require_disclaimer_acceptance()
            serve(
                args.host,
                args.port,
                Path(args.workspace),
                open_browser=not args.no_browser,
                mobile=args.mobile,
            )
        elif args.command == "mobile":
            require_disclaimer_acceptance()
            serve(
                "0.0.0.0",
                args.port,
                Path(args.workspace),
                open_browser=False,
                mobile=True,
                engine_mode="remote_server",
            )
        elif args.command == "standalone":
            require_disclaimer_acceptance()
            from .device_profile import configure_device_profile

            engine_mode = "remote_server" if args.remote_enhanced else "on_device"
            configure_device_profile(
                ram_mb=args.ram_mb,
                engine_mode=engine_mode,
            )
            serve(
                "127.0.0.1",
                args.port,
                Path(args.workspace),
                open_browser=False,
                standalone=True,
                engine_mode=engine_mode,
            )
        elif args.command == "wrapper":
            from .wrappers_info import recommended_wrappers, run_install, wrapper_matrix

            if args.action == "install":
                return run_install()
            matrix = wrapper_matrix()
            recommended = recommended_wrappers()
            _print(
                {
                    "system": sys.platform,
                    "recommended": {key: matrix[key] for key in recommended if key in matrix},
                    "all": matrix,
                    "docs": str(Path(__file__).resolve().parents[1] / "wrappers/README.md"),
                }
            )
        elif args.command == "mcp":
            if args.license_action == "show-key":
                from .edition import generate_demo_license_key

                _print(
                    {
                        "entitlement": "demo",
                        "license_key": generate_demo_license_key(),
                        "license_file_example": {
                            "edition": "pro",
                            "entitlement": "demo",
                            "key": generate_demo_license_key(),
                        },
                    }
                )
                return 0
            from .mcp_server import run_mcp_server

            run_mcp_server()
        elif args.command in {"agent", "codepilot", "pilot"}:
            require_disclaimer_acceptance()
            from .agent import run_code_pilot
            from .agent.providers import AgentError

            if not args.prompt:
                print(
                    "usage: apex agent \"describe what you want\" [--apk path] [--provider openai|ollama|heuristic]",
                    file=sys.stderr,
                )
                return 1
            try:
                result = run_code_pilot(
                    args.prompt,
                    apk_path=args.apk,
                    provider=args.provider,
                    playbook=args.playbook,
                )
            except AgentError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            if args.trace:
                _print(result)
            else:
                print(result["answer"])
                if result.get("trace"):
                    print(
                        f"\n[{result['provider']}] {len(result['trace'])} tool call(s)",
                        file=sys.stderr,
                    )
        return 0
    except (ApexError, EditionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
