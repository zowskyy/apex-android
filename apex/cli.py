"""Command-line interface for APEX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from apex.analysis import ApexError, diff_indexes, inspect_apk
from apex.corpus.stats import corpus_stats
from apex.device.sync import list_connected, sync_device
from apex.format_detect import detect_format
from apex.ios.ipa import is_ipa
from apex.providers.bootstrap import MANAGED_TOOLS, install_tool, list_tools
from apex.providers.bundletool import build_apks, extract_apks, inspect_bundle
from apex.reporting.sarif import security_scan_to_sarif
from apex.signing.display import format_signing_panel
from apex.signing.native import analyze_signatures, cross_check_with_apksigner
from apex.version import __version__
from apex.web import serve
from apex.workflows import (
    PostgresStore,
    SQLiteStore,
    analyze_apk,
    analyze_ios,
    build_project,
    decode_apk,
    decompile_apk,
    diff_apks,
    doctor,
    export_bundle,
    export_icon,
    framework_check,
    generate_sbom,
    jni_report,
    privacy_report,
    roundtrip_verify,
    scan_trackers,
    security_scan,
    verify_apk,
)


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
    parser.add_argument("--version", action="version", version=f"APEX {__version__}")
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
    decompile_cmd.add_argument(
        "--provider",
        choices=["auto", "jadx", "androguard"],
        default="auto",
    )

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
    security_cmd.add_argument(
        "--format",
        choices=["json", "sarif"],
        default="json",
        help="output format for automation pipelines",
    )

    diff_cmd = sub.add_parser("diff", help="semantic APK or report diff")
    diff_cmd.add_argument("left")
    diff_cmd.add_argument("right")
    diff_cmd.add_argument("--output", "-o")

    framework_cmd = sub.add_parser(
        "framework-check", help="check whether compiled-resource rebuild support is available"
    )
    framework_cmd.add_argument("apk")

    sub.add_parser("doctor", help="show parser and external tool availability")

    tools = sub.add_parser("tools", help="manage optional cross-check tools")
    tools_sub = tools.add_subparsers(dest="tools_command", required=True)
    tools_sub.add_parser("list", help="show managed tool catalog and install state")
    tools_install = tools_sub.add_parser("install", help="download and install a managed tool")
    tools_install.add_argument("name", choices=sorted(MANAGED_TOOLS))
    tools_install.add_argument(
        "--skip-checksum",
        action="store_true",
        help="install without verifying the pinned checksum",
    )

    signing_cmd = sub.add_parser("signing", help="certificate and signature detail")
    signing_cmd.add_argument("apk")
    signing_cmd.add_argument("--output", "-o")

    jni_cmd = sub.add_parser(
        "jni", help="resolve the Dalvik/native JNI cross-reference graph"
    )
    jni_cmd.add_argument("apk")
    jni_cmd.add_argument("--output", "-o")

    detect_cmd = sub.add_parser(
        "detect", help="identify a file's real format from its content, not its name"
    )
    detect_cmd.add_argument("app")
    detect_cmd.add_argument("--output", "-o")

    trackers_cmd = sub.add_parser(
        "trackers", help="detect trackers and third-party libraries (APK or IPA)"
    )
    trackers_cmd.add_argument("app")
    trackers_cmd.add_argument("--output", "-o")

    sbom_cmd = sub.add_parser("sbom", help="generate a CycloneDX SBOM (APK or IPA)")
    sbom_cmd.add_argument("app")
    sbom_cmd.add_argument("--out", help="write CycloneDX JSON to a file")

    privacy_cmd = sub.add_parser(
        "privacy", help="cross-platform privacy posture (APK or IPA)"
    )
    privacy_cmd.add_argument("app")
    privacy_cmd.add_argument("--output", "-o")

    ios_cmd = sub.add_parser("ios", help="analyze an iOS .ipa (Mach-O, privacy, trackers)")
    ios_cmd.add_argument("ipa")
    ios_cmd.add_argument("--out", default="apex_ios_out")

    icon_cmd = sub.add_parser("icon", help="export launcher icon from an APK")
    icon_cmd.add_argument("apk")
    icon_cmd.add_argument("-o", "--output", default="icon.png")

    export_cmd = sub.add_parser("export", help="export APK, report, and manifest bundle")
    export_cmd.add_argument("apk")
    export_cmd.add_argument("--out", default="apex_export")

    device = sub.add_parser("device", help="connected-device workflows")
    device_sub = device.add_subparsers(dest="device_command", required=True)
    device_sub.add_parser("list", help="list connected devices")
    pull = device_sub.add_parser("pull", help="pull a package APK set from a device")
    pull.add_argument("package")
    pull.add_argument("--serial", required=True)
    pull.add_argument("--user", type=int, default=0)
    pull.add_argument("--out", default="apex_device_pull")
    sync = device_sub.add_parser("sync", help="incremental device corpus sync")
    sync.add_argument("--serial", required=True)
    sync.add_argument("--user", type=int, default=0)
    sync.add_argument("--db", default=str(Path.home() / ".apex" / "corpus.db"))
    stats = device_sub.add_parser("stats", help="corpus statistics")
    stats.add_argument("--db", default=str(Path.home() / ".apex" / "corpus.db"))
    stats.add_argument("--serial")

    bundle = sub.add_parser("bundle", help="Android App Bundle workflows")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_inspect = bundle_sub.add_parser("inspect", help="dump bundle manifest via bundletool")
    bundle_inspect.add_argument("aab")
    bundle_build = bundle_sub.add_parser("build-apks", help="build APKS from an AAB")
    bundle_build.add_argument("aab")
    bundle_build.add_argument("--out", default="output.apks")
    bundle_extract = bundle_sub.add_parser("extract", help="extract APKs from an APKS archive")
    bundle_extract.add_argument("apks")
    bundle_extract.add_argument("--out", default="apex_apks")

    gui_cmd = sub.add_parser("gui", aliases=["serve"], help="start the local web interface")
    gui_cmd.add_argument("--host", default="127.0.0.1")
    gui_cmd.add_argument("--port", type=int, default=8765)
    gui_cmd.add_argument("--workspace", default=".apex-web")
    gui_cmd.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            path = Path(args.apk)
            if is_ipa(path):
                from apex.ios.ipa import inspect_ipa

                _print(inspect_ipa(path), args.output)
            else:
                _print(inspect_apk(path, include_files=args.files), args.output)
        elif args.command == "analyze" and is_ipa(Path(args.apk)):
            report = analyze_ios(Path(args.apk), Path(args.out))
            print(f"JSON report: {Path(args.out) / 'report.json'}")
            print(
                f"Trackers: {len(report.get('trackers', []))} · "
                f"Posture: {report['privacy_posture']['grade']}"
            )
        elif args.command == "analyze":
            store = (
                SQLiteStore(Path(args.db))
                if args.db
                else (PostgresStore(args.pg) if args.pg else None)
            )
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
                provider=args.provider,
            )
            print(f"Decompiled {len(result['classes'])} classes to {args.out}")
            if result.get("errors"):
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
            payload = security_scan_to_sarif(result) if args.format == "sarif" else result
            _print(payload, args.output)
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
        elif args.command == "doctor":
            _print(doctor())
        elif args.command == "tools":
            if args.tools_command == "list":
                _print(list_tools())
            elif args.tools_command == "install":
                _print(install_tool(args.name, verify_checksum=not args.skip_checksum))
        elif args.command == "signing":
            native = analyze_signatures(Path(args.apk))
            native["cross_check"] = cross_check_with_apksigner(Path(args.apk), native)
            _print(format_signing_panel(native), args.output)
        elif args.command == "jni":
            _print(jni_report(Path(args.apk)), args.output)
        elif args.command == "detect":
            _print(detect_format(Path(args.app)).as_dict(), args.output)
        elif args.command == "trackers":
            _print(scan_trackers(Path(args.app)), args.output)
        elif args.command == "sbom":
            _print(generate_sbom(Path(args.app), Path(args.out) if args.out else None))
        elif args.command == "privacy":
            _print(privacy_report(Path(args.app)), args.output)
        elif args.command == "ios":
            report = analyze_ios(Path(args.ipa), Path(args.out))
            print(f"JSON report: {Path(args.out) / 'report.json'}")
            print(
                f"App: {report['app'].get('bundle_id', '?')} · "
                f"Trackers: {len(report.get('trackers', []))} · "
                f"Posture: {report['privacy_posture']['grade']}"
            )
        elif args.command == "icon":
            _print(export_icon(Path(args.apk), Path(args.output)))
        elif args.command == "export":
            _print(export_bundle(Path(args.apk), Path(args.out)))
        elif args.command == "device":
            if args.device_command == "list":
                _print(list_connected())
            elif args.device_command == "pull":
                from apex.device.pull import pull_to_layout

                result = pull_to_layout(
                    args.serial,
                    args.package,
                    Path(args.out),
                    user_id=args.user,
                )
                _print(
                    {
                        "package": result.package,
                        "destination": result.destination,
                        "artifact_count": result.artifact_count,
                    }
                )
            elif args.device_command == "sync":
                _print(sync_device(args.serial, Path(args.db), user_id=args.user))
            elif args.device_command == "stats":
                _print(corpus_stats(Path(args.db), serial=args.serial))
        elif args.command == "bundle":
            if args.bundle_command == "inspect":
                _print(inspect_bundle(Path(args.aab)))
            elif args.bundle_command == "build-apks":
                _print(build_apks(Path(args.aab), Path(args.out)))
            elif args.bundle_command == "extract":
                _print(extract_apks(Path(args.apks), Path(args.out)))
        elif args.command in {"gui", "serve"}:
            serve(
                args.host,
                args.port,
                Path(args.workspace),
                open_browser=not args.no_browser,
            )
        return 0
    except (ApexError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
