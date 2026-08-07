"""ARC clean-patch hygiene checks (lockfiles, MSRV, community docs, verbose)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from apex.cli import _configure_logging, build_parser

ROOT = Path(__file__).resolve().parents[1]


def test_lockfiles_exist_and_pin_runtime_deps() -> None:
    runtime = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    dev = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    assert "androguard==" in runtime
    assert "Jinja2==" in runtime or "jinja2==" in runtime.lower()
    assert "pytest==" in dev
    assert "ruff==" in dev
    assert (ROOT / "Cargo.lock").is_file()
    assert (ROOT / "scripts" / "generate_lockfiles.sh").is_file()


def test_msrv_declared_in_workspace() -> None:
    cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'^rust-version\s*=\s*"([^"]+)"', cargo, re.M)
    assert match is not None
    assert match.group(1) == "1.74"


def test_community_docs_present() -> None:
    for name in (
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "CHANGELOG.md",
        "SECURITY.md",
    ):
        path = ROOT / name
        assert path.is_file(), name
        assert path.stat().st_size > 100


def test_dockerfile_pins_digest_and_non_root() -> None:
    text = (ROOT / "wrappers" / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "@sha256:" in text
    assert "requirements.lock" in text
    assert "--locked" in text
    assert "USER apex" in text


def test_arc_design_and_harness_manifest() -> None:
    design = ROOT / "docs" / "ARC_CODE_AUDIT_DESIGN.md"
    assert design.is_file()
    text = design.read_text(encoding="utf-8")
    assert "Iterative Zero" in text or "ZERO findings" in text
    assert "Phase 0" in text and "Phase 7" in text
    assert "[SHOW-STOPPER]" in text
    feedback = ROOT / ".cursor" / "FEEDBACK_PROTOCOL.md"
    assert feedback.is_file()
    assert "MAX_AUDIT_ITERATIONS" in feedback.read_text(encoding="utf-8")
    manifest = ROOT / ".cursor" / "audit_input.yaml"
    assert manifest.is_file()
    body = manifest.read_text(encoding="utf-8")
    assert "critical_paths" in body
    assert "max_audit_iterations" in body


def test_build_sh_supports_verbose() -> None:
    text = (ROOT / "build.sh").read_text(encoding="utf-8")
    assert "--verbose" in text
    assert "VERBOSE" in text


def test_cli_verbose_flag_and_logging() -> None:
    parser = build_parser()
    args = parser.parse_args(["-vv", "doctor"])
    assert args.verbose == 2
    _configure_logging(2)
    assert logging.getLogger().level == logging.DEBUG
    _configure_logging(0)
    assert logging.getLogger().level == logging.WARNING
