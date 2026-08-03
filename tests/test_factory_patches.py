"""Tests for scripts/security/scan_apk.py and Chaquopy engine prep."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_workflows import make_apk


def test_scan_apk_wrapper(tmp_path: Path) -> None:
    apk = make_apk(tmp_path / "scan.apk")
    out = tmp_path / "scan-report.json"
    code = subprocess.run(
        [
            sys.executable,
            "scripts/security/scan_apk.py",
            str(apk),
            "-o",
            str(out),
            "--msv",
            "21",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    ).returncode
    assert code in {0, 5}
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["reports"]
    assert "gate_passed" in payload["reports"][0]


def test_prepare_chaquopy_engine_symlink_mode(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "wrappers" / "android" / "prepare_chaquopy_engine.sh"
    env = {"APEX_ENGINE_MODE": "symlink"}
    subprocess.run(["bash", str(script)], cwd=root, env={**env, **dict(__import__("os").environ)}, check=True)
    apex_link = root / "wrappers" / "android" / "standalone" / "app" / "src" / "main" / "python" / "apex"
    assert apex_link.exists()


@pytest.mark.skipif(not Path("/usr/bin/python3.10").exists(), reason="python3.10 required for wheel mode")
def test_prepare_chaquopy_engine_wheel_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "wrappers" / "android" / "prepare_chaquopy_engine.sh"
    env = {"APEX_ENGINE_MODE": "wheel"}
    subprocess.run(
        ["bash", str(script)],
        cwd=root,
        env={**env, **dict(__import__("os").environ)},
        check=True,
    )
    wheel = root / "wrappers" / "android" / "standalone" / "core-wheel.whl"
    assert wheel.is_file()
    # restore symlink mode for other tests
    subprocess.run(
        ["bash", str(script)],
        cwd=root,
        env={"APEX_ENGINE_MODE": "symlink", **dict(__import__("os").environ)},
        check=True,
    )
