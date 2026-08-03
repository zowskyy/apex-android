"""Pytest configuration for APEX."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_audit_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep gate audit JSONL per-test (avoids cross-test pollution)."""
    monkeypatch.setenv("APEX_AUDIT_DIR", str(tmp_path / "apex-audit"))
