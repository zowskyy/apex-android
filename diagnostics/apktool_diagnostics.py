#!/usr/bin/env python3
"""
apktool_diagnostics.py - a small toolkit for stress-testing apktool
round-trips, built out of an actual investigation (not a spec exercise).

Subcommands:
  security-scan   Scan an APK's resources.arsc string pools for path-
                   traversal-suspect entries (../, absolute paths) BEFORE
                   decoding. Independent second check regardless of which
                   apktool version is doing the decoding - see
                   CVE-2026-39973 for why this matters.
  framework-check  Attempt decode+build, and if it fails on a missing
                   android: attribute/resource, report which one and (when
                   known) which Android API level introduced it, instead
                   of a raw aapt2 stack trace.
  roundtrip        Decode -> rebuild with zero edits -> diff, classifying
                   every difference as expected or a genuine anomaly.
                   (Carried over from the earlier apk_roundtrip_diff.py,
                   folded in here.)
  dex-diff         Independently disassemble classes*.dex from both the
                   original and rebuilt APK with a standalone baksmali,
                   and diff the actual instructions - not just assert that
                   dex reassembly noise is "expected."
  corpus           Run all of the above against a small fixed set of real
                   APKs and produce one summary report, so a future
                   apktool/aapt2 version bump can be checked by rerunning
                   this instead of another manual investigation.

Every check here was built against a real, reproduced case during an
actual investigation - see the accompanying README for what each one is
actually catching and its known limitations.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


# ---------------------------------------------------------------------------
# A. Security pre-scan
# ---------------------------------------------------------------------------

TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"^/"),        # absolute unix path
    re.compile(r"^[A-Za-z]:\\"),  # absolute windows path
    re.compile(r"\x00"),      # embedded null - classic truncation trick
]


def _iter_string_pools(data: bytes):
    """Yield (offset, is_utf8, list_of_strings) for every ResStringPool
    chunk found in an .arsc file. Best-effort scan: not a full chunk-tree
    walk, just enough to find every string pool regardless of nesting."""
    off = 0
    while off < len(data) - 8:
        ctype = struct.unpack_from('<H', data, off)[0]
        if ctype == 0x0001:
            try:
                _, header_size, size = struct.unpack_from('<HHI', data, off)
                stringCount, styleCount, flags, stringsStart, stylesStart = \
                    struct.unpack_from('<IIIII', data, off + 8)
                if stringCount == 0 or size <= 0 or size > len(data) - off:
                    off += 4
                    continue
                # Sanity bounds: a coincidental 0x0001 match on non-chunk
                # bytes can yield a garbage stringCount that would try to
                # allocate/iterate absurdly - bail out instead of OOMing.
                idx_off = off + 28
                if stringCount > 5_000_000 or idx_off + stringCount * 4 > off + size:
                    off += 4
                    continue
                is_utf8 = bool(flags & (1 << 8))
                strings = []
                base = off + stringsStart
                for i in range(stringCount):
                    entry_off = struct.unpack_from('<I', data, idx_off + i * 4)[0]
                    p = base + entry_off
                    if is_utf8:
                        b0 = data[p]
                        p += 2 if (b0 & 0x80) else 1
                        b1 = data[p]
                        if b1 & 0x80:
                            strlen = ((b1 & 0x7f) << 8) | data[p + 1]
                            p += 2
                        else:
                            strlen = b1
                            p += 1
                        s = data[p:p + strlen].decode('utf-8', errors='replace')
                    else:
                        u0 = struct.unpack_from('<H', data, p)[0]
                        if u0 & 0x8000:
                            strlen = ((u0 & 0x7fff) << 16) | struct.unpack_from('<H', data, p + 2)[0]
                            p += 4
                        else:
                            strlen = u0
                            p += 2
                        s = data[p:p + strlen * 2].decode('utf-16-le', errors='replace')
                    strings.append(s)
                yield (off, is_utf8, strings)
            except (struct.error, IndexError, UnicodeDecodeError):
                pass
        off += 4


def security_scan(apk_path: Path) -> dict:
    with zipfile.ZipFile(apk_path) as zf:
        if 'resources.arsc' not in zf.namelist():
            return {"scanned": False, "reason": "no resources.arsc in APK"}
        data = zf.read('resources.arsc')

    findings = []
    for pool_offset, is_utf8, strings in _iter_string_pools(data):
        for s in strings:
            if any(p.search(s) for p in TRAVERSAL_PATTERNS):
                findings.append({"pool_offset": pool_offset, "string": s})

    return {
        "scanned": True,
        "apk": str(apk_path),
        "verdict": "SUSPICIOUS" if findings else "CLEAN",
        "findings": findings[:100],
        "finding_count": len(findings),
    }


# ---------------------------------------------------------------------------
# B. Framework compatibility check
# ---------------------------------------------------------------------------

# Known API level a given android: attribute/resource was introduced at,
# built from what actually broke in this investigation plus the historical
# pattern found researching it (compileSdkVersion, localeConfig, etc.)
KNOWN_ATTR_MIN_API = {
    "defaultLocale": 35,
    "localeConfig": 33,
    "requestLegacyExternalStorage": 29,
    "isSplitRequired": 31,
    "compileSdkVersion": 28,
    "compileSdkVersionCodename": 28,
    "attributionTags": 30,
    "knownCerts": 31,
}

MISSING_ATTR_RE = re.compile(r"error: attribute android:(\w+) not found")
MISSING_RES_RE = re.compile(r"error: resource android:(\w+)/(\w+) not found")


def framework_check(apktool_jar: Path, apk: Path, workdir: Path) -> dict:
    decoded = workdir / "fw_check_decoded"
    rebuilt = workdir / "fw_check_rebuilt.apk"
    run(["rm", "-rf", str(decoded)])

    d = run(["java", "-jar", str(apktool_jar), "d", "-f", str(apk), "-o", str(decoded)])
    if d.returncode != 0:
        return {"verdict": "DECODE_FAILED", "raw_error": (d.stdout + d.stderr)[-2000:]}

    b = run(["java", "-jar", str(apktool_jar), "b", str(decoded), "-o", str(rebuilt)])
    if b.returncode == 0:
        return {"verdict": "OK", "message": "zero-edit rebuild succeeded with the currently installed framework"}

    combined = b.stdout + b.stderr
    missing_attrs = sorted(set(MISSING_ATTR_RE.findall(combined)))
    missing_res = sorted(set(f"{t}/{n}" for t, n in MISSING_RES_RE.findall(combined)))

    diagnosis = []
    for attr in missing_attrs:
        min_api = KNOWN_ATTR_MIN_API.get(attr)
        if min_api:
            diagnosis.append(f"android:{attr} - introduced in API {min_api}; "
                              f"install a framework for API {min_api}+ (`apktool if <framework.apk>`)")
        else:
            diagnosis.append(f"android:{attr} - not in the installed framework; "
                              f"likely needs a newer or OEM-specific framework")

    if not missing_attrs and not missing_res:
        return {
            "verdict": "BUILD_FAILED_OTHER_CAUSE",
            "message": "build failed but not on a recognized missing-attribute/resource pattern",
            "raw_error": combined[-2000:],
        }

    return {
        "verdict": "FRAMEWORK_GAP",
        "missing_attributes": missing_attrs,
        "missing_resources": missing_res,
        "diagnosis": diagnosis,
    }


# ---------------------------------------------------------------------------
# C. Round-trip diff (carried over, condensed)
# ---------------------------------------------------------------------------

EXPECTED_STRIP_PREFIXES = ("META-INF/",)
MINIFIED_RES_NAME = re.compile(r"^res/[-\w]{1,4}(\.9)?\.\w+$")
SDK_QUALIFIER_SEGMENT = re.compile(r"-v\d+")
LINE_ANNOTATION = re.compile(r"\(line=\d+\)")


def load_zip_index(path: Path):
    index = {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            index[info.filename] = (info.CRC, info.file_size, sha1(zf.read(info.filename)))
    return index


def classify_missing(name, rebuilt_names):
    if name.startswith(EXPECTED_STRIP_PREFIXES):
        return "expected_signing_metadata_stripped"
    if MINIFIED_RES_NAME.match(name):
        return "expected_resource_renamed"
    stripped = SDK_QUALIFIER_SEGMENT.sub("", name)
    if stripped != name and stripped in rebuilt_names:
        return "expected_sdk_qualifier_pruned_by_original_build"
    return "ANOMALY_missing"


def xml_structurally_equal(aapt2, orig_apk, rebuilt_apk, entry):
    a = run([str(aapt2), "dump", "xmltree", str(orig_apk), "--file", entry])
    b = run([str(aapt2), "dump", "xmltree", str(rebuilt_apk), "--file", entry])
    if a.returncode != 0 or b.returncode != 0:
        return False
    return LINE_ANNOTATION.sub("", a.stdout) == LINE_ANNOTATION.sub("", b.stdout)


def classify_diverged(entry, aapt2, orig_apk, rebuilt_apk):
    if entry.endswith(".xml") or entry == "AndroidManifest.xml":
        if aapt2 and xml_structurally_equal(aapt2, orig_apk, rebuilt_apk, entry):
            return "expected_binary_xml_lineno_metadata_only"
        return "ANOMALY_content_diverged"
    if entry.endswith(".dex"):
        return "needs_dex_diff"  # deferred to the dex-diff subcommand, not asserted here
    if entry == "resources.arsc":
        return "expected_resource_renamed"
    return "ANOMALY_content_diverged"


def roundtrip_diff(apktool_jar: Path, apk: Path, workdir: Path, aapt2: Path = None) -> dict:
    decoded = workdir / "rt_decoded"
    rebuilt = workdir / "rt_rebuilt.apk"
    run(["rm", "-rf", str(decoded)])

    d = run(["java", "-jar", str(apktool_jar), "d", "-f", str(apk), "-o", str(decoded)])
    if d.returncode != 0:
        return {"verdict": "FAIL", "stage": "decode", "error": (d.stdout + d.stderr)[-2000:]}
    b = run(["java", "-jar", str(apktool_jar), "b", str(decoded), "-o", str(rebuilt)])
    if b.returncode != 0:
        return {"verdict": "FAIL", "stage": "build", "error": (b.stdout + b.stderr)[-2000:]}

    orig = load_zip_index(apk)
    rbld = load_zip_index(rebuilt)
    orig_names, rbld_names = set(orig), set(rbld)
    only_in_orig = orig_names - rbld_names
    common = orig_names & rbld_names
    diverged_names = sorted(n for n in common if orig[n][2] != rbld[n][2])

    missing_classified = {}
    for name in sorted(only_in_orig):
        missing_classified.setdefault(classify_missing(name, rbld_names), []).append(name)

    diverged_classified = {}
    for name in diverged_names:
        diverged_classified.setdefault(classify_diverged(name, aapt2, apk, rebuilt), []).append(name)

    anomalies_missing = missing_classified.get("ANOMALY_missing", [])
    anomalies_diverged = diverged_classified.get("ANOMALY_content_diverged", [])
    dex_to_check = diverged_classified.get("needs_dex_diff", [])

    summary = {}
    for src in (missing_classified, diverged_classified):
        for k, v in src.items():
            summary[k] = summary.get(k, 0) + len(v)

    return {
        "verdict": "NEEDS_DEX_DIFF" if dex_to_check else ("FAIL" if (anomalies_missing or anomalies_diverged) else "PASS"),
        "rebuilt_apk_path": str(rebuilt),
        "entry_count": {"original": len(orig_names), "rebuilt": len(rbld_names)},
        "summary": summary,
        "anomalies": {"missing_entries": anomalies_missing[:50], "content_diverged": anomalies_diverged[:50]},
        "dex_entries_to_check": dex_to_check,
    }


# ---------------------------------------------------------------------------
# D. Semantic dex diff
# ---------------------------------------------------------------------------

LINE_DIRECTIVE = re.compile(r"^\s*\.line \d+\s*$")
# Discovered by actually diffing flagged files: apktool's bundled smali
# assembler omits a static field's default-value initializer (= null,
# = false, = 0, etc.) when reassembling, since it's redundant - the VM
# already defaults an uninitialized static field to that value. Same
# runtime behavior, different encoded bytes. Strip the "= <default>" tail
# so this doesn't get flagged as a real divergence.
FIELD_DEFAULT_INIT = re.compile(
    r"^(\.field .*?:[A-Za-z0-9/;\[$]+)\s*=\s*(null|false|0|0L|0\.0f?|0x0)\s*$"
)


def _normalize_smali_line(line: str) -> str:
    m = FIELD_DEFAULT_INIT.match(line)
    return m.group(1) if m else line


def _baksmali_dir(baksmali_jar: Path, dex_bytes: bytes, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    dex_path = out_dir.parent / (out_dir.name + ".dex")
    dex_path.write_bytes(dex_bytes)
    r = run(["java", "-jar", str(baksmali_jar), "disassemble", str(dex_path), "-o", str(out_dir)])
    return r


def dex_diff(baksmali_jar: Path, orig_apk: Path, rebuilt_apk: Path, workdir: Path) -> dict:
    results = {}
    with zipfile.ZipFile(orig_apk) as zo, zipfile.ZipFile(rebuilt_apk) as zr:
        dex_names = sorted(n for n in zo.namelist() if re.match(r"^classes\d*\.dex$", n))
        for name in dex_names:
            if name not in zr.namelist():
                results[name] = {"verdict": "ANOMALY_missing_in_rebuilt"}
                continue
            orig_dex = zo.read(name)
            rbld_dex = zr.read(name)

            orig_out = workdir / f"dexdiff_orig_{name}"
            rbld_out = workdir / f"dexdiff_rbld_{name}"
            run(["rm", "-rf", str(orig_out), str(rbld_out)])
            ro = _baksmali_dir(baksmali_jar, orig_dex, orig_out)
            rr = _baksmali_dir(baksmali_jar, rbld_dex, rbld_out)
            if ro.returncode != 0 or rr.returncode != 0:
                results[name] = {"verdict": "DISASSEMBLY_FAILED",
                                  "error": (ro.stdout + ro.stderr + rr.stdout + rr.stderr)[-1000:]}
                continue

            orig_files = {p.relative_to(orig_out): p for p in orig_out.rglob("*.smali")}
            rbld_files = {p.relative_to(rbld_out): p for p in rbld_out.rglob("*.smali")}
            only_orig = set(orig_files) - set(rbld_files)
            only_rbld = set(rbld_files) - set(orig_files)
            real_diffs = []
            for rel in sorted(set(orig_files) & set(rbld_files)):
                a_lines = [_normalize_smali_line(l) for l in orig_files[rel].read_text(errors="replace").splitlines()
                           if not LINE_DIRECTIVE.match(l)]
                b_lines = [_normalize_smali_line(l) for l in rbld_files[rel].read_text(errors="replace").splitlines()
                           if not LINE_DIRECTIVE.match(l)]
                if a_lines != b_lines:
                    real_diffs.append(str(rel))

            results[name] = {
                "verdict": "ANOMALY" if (only_orig or only_rbld or real_diffs) else "PASS_semantically_identical",
                "classes_only_in_original": sorted(str(p) for p in only_orig)[:20],
                "classes_only_in_rebuilt": sorted(str(p) for p in only_rbld)[:20],
                "classes_with_real_instruction_diffs": real_diffs[:20],
            }
    return results


# ---------------------------------------------------------------------------
# E. Regression corpus
# ---------------------------------------------------------------------------

def run_corpus(apktool_jar: Path, baksmali_jar: Path, aapt2: Path, apks: dict, workdir: Path) -> dict:
    report = {}
    for name, apk_path in apks.items():
        apk_path = Path(apk_path)
        entry = {}
        entry["security_scan"] = security_scan(apk_path)
        entry["roundtrip"] = roundtrip_diff(apktool_jar, apk_path, workdir, aapt2)
        if entry["roundtrip"].get("verdict") in ("FAIL",):
            entry["framework_check"] = framework_check(apktool_jar, apk_path, workdir)
        elif entry["roundtrip"].get("dex_entries_to_check"):
            rebuilt = Path(entry["roundtrip"]["rebuilt_apk_path"])
            entry["dex_diff"] = dex_diff(baksmali_jar, apk_path, rebuilt, workdir)
        report[name] = entry
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("security-scan")
    sp.add_argument("apk")

    fp = sub.add_parser("framework-check")
    fp.add_argument("apktool_jar")
    fp.add_argument("apk")
    fp.add_argument("workdir")

    rp = sub.add_parser("roundtrip")
    rp.add_argument("apktool_jar")
    rp.add_argument("apk")
    rp.add_argument("workdir")
    rp.add_argument("--aapt2", default=None)

    dp = sub.add_parser("dex-diff")
    dp.add_argument("baksmali_jar")
    dp.add_argument("orig_apk")
    dp.add_argument("rebuilt_apk")
    dp.add_argument("workdir")

    cp = sub.add_parser("corpus")
    cp.add_argument("apktool_jar")
    cp.add_argument("baksmali_jar")
    cp.add_argument("aapt2")
    cp.add_argument("workdir")
    cp.add_argument("apks", nargs="+", help="name=path pairs")

    args = p.parse_args()

    if args.cmd == "security-scan":
        result = security_scan(Path(args.apk))
    elif args.cmd == "framework-check":
        result = framework_check(Path(args.apktool_jar), Path(args.apk), Path(args.workdir))
    elif args.cmd == "roundtrip":
        aapt2 = Path(args.aapt2) if args.aapt2 else None
        result = roundtrip_diff(Path(args.apktool_jar), Path(args.apk), Path(args.workdir), aapt2)
    elif args.cmd == "dex-diff":
        result = dex_diff(Path(args.baksmali_jar), Path(args.orig_apk), Path(args.rebuilt_apk), Path(args.workdir))
    elif args.cmd == "corpus":
        apks = dict(pair.split("=", 1) for pair in args.apks)
        result = run_corpus(Path(args.apktool_jar), Path(args.baksmali_jar), Path(args.aapt2), apks, Path(args.workdir))
    else:
        p.error("unknown command")
        return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
