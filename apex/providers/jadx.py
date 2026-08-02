"""jadx CLI provider for Java decompilation."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from apex.analysis import ApexError, descriptor_to_java

from .registry import get_jadx_command
from .runner import run_tool
from .types import ProvenanceCollector, ProvenanceRecord, timed_operation


def jadx_version() -> str | None:
    command = get_jadx_command()
    if not command:
        return None
    try:
        result = run_tool([*command, "--version"], timeout=30)
        text = (result.stdout + result.stderr).strip()
        return text.splitlines()[0][:80] if text else None
    except ApexError:
        return None


def decompile_apk_jadx(
    apk_path: Path,
    out_dir: Path,
    *,
    collector: ProvenanceCollector | None = None,
    single_class: str | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    command = get_jadx_command()
    if not command:
        raise ApexError("jadx not found; install jadx or set APEX_JADX")
    apk_path, out_dir = Path(apk_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = jadx_version()
    collector = collector or ProvenanceCollector()
    with timed_operation(collector, "decompile.java", "jadx", version) as op:
        with tempfile.TemporaryDirectory(prefix="apex-jadx-") as tmp:
            work = Path(tmp) / "out"
            argv = [
                *command,
                "--no-res",
                "--no-imports",
                "--threads-count",
                "4",
                "-d",
                str(work),
            ]
            if single_class:
                argv.extend(["--single-class", single_class, "--single-class-output", str(out_dir)])
            argv.append(str(apk_path))
            result = run_tool(argv, timeout=timeout)
            if result.returncode:
                op.status = "error"
                op.reason = (result.stdout + result.stderr)[-1000:]
                raise ApexError(f"jadx failed:\n{op.reason}")
            if not single_class:
                for path in work.rglob("*"):
                    if path.is_file():
                        relative = path.relative_to(work)
                        destination = out_dir / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, destination)
    index = _index_java_tree(apk_path, out_dir)
    index["provider"] = "jadx"
    return index


def _index_java_tree(apk_path: Path, out_dir: Path) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    for java_file in sorted(out_dir.rglob("*.java")):
        relative = java_file.relative_to(out_dir).as_posix()
        class_name = relative[:-5].replace("/", ".")
        classes.append(
            {
                "name": class_name,
                "java": relative,
                "dex": "",
                "obfuscated_name": "",
            }
        )
    return {"apk": str(apk_path), "dex_files": [], "classes": classes, "errors": []}


def decompile_class_androguard_fallback(
    apk_path: Path,
    out_dir: Path,
    *,
    collector: ProvenanceCollector,
    emit_smali: bool = False,
) -> dict[str, Any]:
    """Reuse workflows-style Androguard decompilation as fallback."""
    import re
    import zipfile

    from apex.analysis import load_dex
    from apex.workflows import _method_smali, _safe_source_path

    apk_path, out_dir = Path(apk_path), Path(out_dir)
    java_dir = out_dir / "java"
    java_dir.mkdir(parents=True, exist_ok=True)
    version = None
    try:
        import androguard

        version = getattr(androguard, "__version__", "installed")
    except ImportError:
        pass
    with timed_operation(
        collector,
        "decompile.java",
        "androguard",
        version,
        fallback_from="jadx",
    ) as op:
        index: dict[str, Any] = {"apk": str(apk_path), "dex_files": [], "classes": [], "errors": []}
        with zipfile.ZipFile(apk_path) as archive:
            dex_names = sorted(
                name for name in archive.namelist() if re.fullmatch(r"(?:.*/)?classes\d*\.dex", name)
            )
            for dex_name in dex_names:
                try:
                    dex, _ = load_dex(archive.read(dex_name), with_decompiler=True)
                except Exception as exc:
                    index["errors"].append({"dex": dex_name, "error": str(exc)})
                    continue
                index["dex_files"].append(dex_name)
                for cls in dex.get_classes():
                    descriptor = str(cls.get_name())
                    display_name = descriptor_to_java(descriptor)
                    class_entry: dict[str, Any] = {
                        "dex": dex_name,
                        "name": display_name,
                        "obfuscated_name": "",
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
                        smali_dir = out_dir / "smali"
                        smali_dir.mkdir(parents=True, exist_ok=True)
                        destination = smali_dir / _safe_source_path(display_name, ".smali")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        header = f".class {cls.get_access_flags_string()} {descriptor}\n"
                        header += f".super {cls.get_superclassname()}\n\n"
                        body = "".join(_method_smali(method) + "\n" for method in cls.get_methods())
                        destination.write_text(header + body, encoding="utf-8")
                        class_entry["smali"] = destination.relative_to(out_dir).as_posix()
                    index["classes"].append(class_entry)
        if index["errors"]:
            op.mark_fallback("partial Androguard decompile errors")
        index["provider"] = "androguard"
        return index
