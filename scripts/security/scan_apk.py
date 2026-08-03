#!/usr/bin/env python3
"""Release/CI APK security wrapper — runs apex gate + security-scan on packaged APKs.

Usage:
  python scripts/security/scan_apk.py path/to.apk [path/to2.apk ...]
  python scripts/security/scan_apk.py release-staging/android/*.apk

Writes scan-apk-report.json beside the first APK (or -o path).
Exit 0 if gate passes at candidate stage; non-zero if gate --ci would fail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apex.gate import run_hard_gate
from apex.workflows import security_scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="APEX gate + security-scan on release APK(s)")
    parser.add_argument("apk", nargs="+", help="APK file path(s)")
    parser.add_argument("--msv", type=int, default=21)
    parser.add_argument("--stage", default="candidate")
    parser.add_argument("-o", "--output", help="Combined JSON report path")
    args = parser.parse_args(argv)

    reports: list[dict] = []
    exit_code = 0

    for raw in args.apk:
        apk = Path(raw)
        if not apk.is_file():
            print(f"scan_apk: missing file: {apk}", file=sys.stderr)
            return 1
        sec = security_scan(apk)
        gate = run_hard_gate(apk, msv=args.msv, stage=args.stage)
        block = {
            "apk": str(apk.resolve()),
            "security_scan": sec,
            "gate": gate.to_dict(),
            "gate_passed": gate.gate_passed,
        }
        reports.append(block)
        if not gate.gate_passed:
            exit_code = 5
        print(f"{apk.name}: gate_passed={gate.gate_passed} score={gate.score:.1f} verdict={sec.get('verdict')}")

    out = Path(args.output) if args.output else Path(args.apk[0]).parent / "scan-apk-report.json"
    out.write_text(json.dumps({"reports": reports}, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
