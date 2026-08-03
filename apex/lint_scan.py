"""YAML-driven regex lint over decompiled Java (blueprint LINT-1)."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

_DEFAULT_RULES = Path(__file__).resolve().parent / "lint_rules.yaml"
_MAX_FILE_BYTES = 256 * 1024


def _parse_yaml_rules(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_rules = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "rules:":
            in_rules = True
            continue
        if not in_rules:
            continue
        if stripped.startswith("- id:"):
            if current:
                rules.append(current)
            current = {"id": stripped.split(":", 1)[1].strip()}
            continue
        if current is None:
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key in {"pattern", "message", "applies_to", "severity", "id"}:
                current[key] = value
    if current:
        rules.append(current)
    return rules


def load_lint_rules(path: Path | None = None) -> list[dict[str, Any]]:
    rules_path = path or _DEFAULT_RULES
    if not rules_path.is_file():
        return []
    return _parse_yaml_rules(rules_path.read_text(encoding="utf-8"))


def _matches_glob(path: Path, pattern: str) -> bool:
    return fnmatch.fnmatch(path.as_posix(), pattern.replace("**/", "")) or fnmatch.fnmatch(
        path.name, pattern.split("/")[-1]
    )


def scan_java_tree(
    root: Path,
    rules: list[dict[str, Any]] | None = None,
    *,
    max_files: int = 400,
) -> list[dict[str, Any]]:
    root = Path(root)
    if not root.is_dir():
        return []
    rule_set = rules or load_lint_rules()
    compiled: list[tuple[dict[str, Any], re.Pattern[str]]] = []
    for rule in rule_set:
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            compiled.append((rule, re.compile(pattern, re.IGNORECASE | re.DOTALL)))
        except re.error:
            continue

    findings: list[dict[str, Any]] = []
    count = 0
    for java_file in sorted(root.rglob("*.java")):
        if count >= max_files:
            break
        count += 1
        try:
            text = java_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > _MAX_FILE_BYTES:
            text = text[:_MAX_FILE_BYTES]
        for rule, regex in compiled:
            glob = str(rule.get("applies_to", "**/*.java"))
            if not _matches_glob(java_file.relative_to(root), glob):
                continue
            if regex.search(text):
                findings.append(
                    {
                        "severity": rule.get("severity", "medium"),
                        "category": f"lint-{rule.get('id', 'rule')}",
                        "message": str(rule.get("message", "")),
                        "evidence": java_file.relative_to(root).as_posix(),
                    }
                )
    return findings


def scan_apk_lint(
    apk_path: Path,
    workspace: Path,
    *,
    max_decompile_classes: int = 150,
) -> list[dict[str, Any]]:
    """Decompile (capped) then run lint rules — used by gate in workspace."""
    from apex.workflows import decompile_apk

    apk_path = Path(apk_path)
    workspace = Path(workspace)
    out = workspace / f".lint-{apk_path.stem}"
    try:
        result = decompile_apk(apk_path, out)
        if not result.get("classes"):
            return []
        java_root = out / "java"
        if not java_root.is_dir():
            return []
        return scan_java_tree(java_root)
    except Exception:
        return []
