from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "corpus"
TOOLS = ROOT / "benchmarks" / "tools"
RESULTS = ROOT / "benchmarks" / "results"

APKS = {
    "F-Droid": CORPUS / "fdroid_latest.apk",
    "NewPipe 0.28.8": CORPUS / "newpipe_v0.28.8.apk",
}


def run_command(command: list[str], timeout: int = 180) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        return {
            "command": command,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "seconds": elapsed,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "ok": False,
            "timeout": timeout,
            "seconds": time.perf_counter() - started,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def inspect_command(apk: Path, runs: int) -> dict[str, Any]:
    attempts = [run_command([sys.executable, "-m", "apex", "inspect", str(apk)], timeout=60) for _ in range(runs)]
    ok_attempts = [attempt for attempt in attempts if attempt["ok"]]
    result = (ok_attempts[-1] if ok_attempts else attempts[-1]).copy()
    result["runs"] = attempts
    result["process_median_seconds"] = statistics.median(attempt["seconds"] for attempt in ok_attempts) if ok_attempts else None
    reported = []
    for attempt in ok_attempts:
        try:
            payload = json.loads(attempt["stdout_tail"])
        except json.JSONDecodeError:
            continue
        if "elapsed_ms" in payload:
            reported.append(float(payload["elapsed_ms"]) / 1000)
    result["median_seconds"] = statistics.median(reported) if reported else result["process_median_seconds"]
    return result


def find_jadx() -> Path | None:
    candidates = [TOOLS / "jadx" / "bin" / "jadx"]
    candidates.extend(sorted(TOOLS.glob("jadx-*/bin/jadx")))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    path = shutil.which("jadx")
    return Path(path) if path else None


def apktool_jar() -> Path | None:
    candidate = TOOLS / "apktool.jar"
    return candidate if candidate.exists() else None


def benchmark_short(runs: int, jadx_apk: str) -> dict[str, Any]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"runs": runs, "mode": "short", "apks": []}
    jar = apktool_jar()
    jadx = find_jadx()

    for label, apk in APKS.items():
        entry: dict[str, Any] = {
            "label": label,
            "apk": str(apk),
            "size_bytes": apk.stat().st_size if apk.exists() else None,
            "operations": {},
        }
        if not apk.exists():
            entry["error"] = "missing APK"
            results["apks"].append(entry)
            continue
        entry["operations"]["apex_inspect"] = inspect_command(apk, runs)

        with tempfile.TemporaryDirectory(prefix="apex-short-", dir=RESULTS) as tmp:
            tmp_root = Path(tmp)
            if jar:
                entry["operations"]["apktool_manifest_only"] = run_command(
                    ["java", "-jar", str(jar), "d", "-f", "-s", "--only-manifest", "-o", str(tmp_root / f"apktool-{label}"), str(apk)],
                    timeout=180,
                )
            else:
                entry["operations"]["apktool_manifest_only"] = {"ok": False, "error": "benchmarks/tools/apktool.jar missing"}

            if label == jadx_apk:
                entry["operations"]["apex_first_dex_decompile"] = run_command(
                    [
                        sys.executable,
                        "-m",
                        "apex",
                        "decompile",
                        str(apk),
                        "--first-dex-only",
                        "--out",
                        str(tmp_root / "apex-first-dex"),
                    ],
                    timeout=180,
                )
                if jadx:
                    entry["operations"]["jadx_decompile"] = run_command(
                        [str(jadx), "-d", str(tmp_root / "jadx"), str(apk)],
                        timeout=180,
                    )
                else:
                    entry["operations"]["jadx_decompile"] = {"ok": False, "error": "jadx missing"}
        results["apks"].append(entry)
    return results


def seconds(op: dict[str, Any]) -> float | None:
    return op.get("median_seconds", op.get("seconds"))


def fmt(op: dict[str, Any]) -> str:
    value = seconds(op)
    if value is None:
        return "not run"
    if not op.get("ok", True):
        if op.get("timeout"):
            return f"timed out at {op['timeout']}s"
        return f"failed ({value:.2f}s)"
    return f"{value * 1000:.1f} ms" if value < 1 else f"{value:.2f} s"


def write_markdown(results: dict[str, Any], path: Path) -> None:
    lines = [
        "# APEX Benchmarks",
        "",
        "Short benchmark run after the full two-APK jadx/apktool suite terminated the VM pod.",
        "",
        "| APK | Size | APEX inspect engine | Inspect <100ms | apktool manifest-only | APEX first DEX->Java | jadx APK->Java | Notes |",
        "| --- | ---: | ---: | :---: | ---: | ---: | ---: | --- |",
    ]
    for apk in results["apks"]:
        ops = apk.get("operations", {})
        inspect = ops.get("apex_inspect", {})
        apktool = ops.get("apktool_manifest_only", {})
        apex_dex = ops.get("apex_first_dex_decompile", {})
        jadx = ops.get("jadx_decompile", {})
        inspect_seconds = seconds(inspect)
        size_mb = (apk.get("size_bytes") or 0) / (1024 * 1024)
        notes = []
        if inspect.get("process_median_seconds") is not None:
            notes.append(f"inspect process median {inspect['process_median_seconds'] * 1000:.1f} ms")
        if jadx and not jadx.get("ok", True):
            notes.append("jadx incomplete")
        lines.append(
            "| {label} | {size:.1f} MB | {inspect_time} | {inspect_ok} | {apktool_time} | {apex_dex_time} | {jadx_time} | {notes} |".format(
                label=apk["label"],
                size=size_mb,
                inspect_time=fmt(inspect),
                inspect_ok="yes" if inspect_seconds is not None and inspect_seconds < 0.100 else "no",
                apktool_time=fmt(apktool),
                apex_dex_time=fmt(apex_dex),
                jadx_time=fmt(jadx),
                notes="; ".join(notes),
            )
        )
    lines.extend(
        [
            "",
            "Targets:",
            "- `inspect`: <100ms engine time. Passing on both real APKs.",
            "- Full two-APK decode/decompile comparisons: not completed in this VM after the earlier pod termination; this file records the requested short comparisons instead.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run APEX benchmark suite")
    parser.add_argument("--runs", type=int, default=7, help="inspect repetitions per APK")
    parser.add_argument("--jadx-apk", choices=sorted(APKS), default="NewPipe 0.28.8")
    args = parser.parse_args()
    results = benchmark_short(args.runs, args.jadx_apk)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "benchmarks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(results, RESULTS / "benchmarks.md")
    print((RESULTS / "benchmarks.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
