"""Acceptable-use disclaimer acceptance."""

from apex.disclaimer import (
    DISCLAIMER_VERSION,
    accept_disclaimer,
    disclaimer_accepted,
    disclaimer_path,
)


def test_disclaimer_accept_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APEX_LICENSE_DIR", str(tmp_path))
    assert not disclaimer_accepted()
    accept_disclaimer()
    assert disclaimer_accepted()
    assert disclaimer_path().is_file()
    data = disclaimer_path().read_text(encoding="utf-8")
    assert f'"version": {DISCLAIMER_VERSION}' in data
