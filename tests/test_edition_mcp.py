"""Edition, licensing, and MCP server tests."""


import pytest

from apex.edition import (
    Edition,
    EditionError,
    Feature,
    active_edition,
    edition_info,
    generate_demo_license_key,
    generate_license_key,
    has_feature,
    read_license_record,
    require_feature,
)


def test_community_edition_features():
    assert active_edition() == Edition.COMMUNITY
    assert has_feature(Feature.INSPECT)
    assert has_feature(Feature.WEB_UI)
    assert not has_feature(Feature.MCP_SERVER)
    assert not has_feature(Feature.POSTGRES_STORE)


def test_pro_license_from_environment(monkeypatch):
    key = generate_license_key("demo")
    monkeypatch.setenv("APEX_LICENSE_KEY", key)
    monkeypatch.setenv("APEX_ENTITLEMENT", "demo")
    monkeypatch.delenv("APEX_LICENSE_FILE", raising=False)
    assert read_license_record() is not None
    assert active_edition() == Edition.PRO
    assert has_feature(Feature.MCP_SERVER)
    assert has_feature(Feature.CODE_PILOT)


def test_invalid_license_is_rejected(monkeypatch):
    monkeypatch.setenv("APEX_LICENSE_KEY", "APEX-PRO-INVALIDKEY0000")
    monkeypatch.setenv("APEX_ENTITLEMENT", "demo")
    assert read_license_record() is None
    assert active_edition() == Edition.COMMUNITY


def test_require_feature_raises_for_community():
    with pytest.raises(EditionError):
        require_feature(Feature.MCP_SERVER)


def test_demo_license_key_is_stable():
    assert generate_demo_license_key() == generate_license_key("demo")


def test_edition_info_includes_demo_key():
    info = edition_info()
    assert info["edition"] == Edition.COMMUNITY.value
    assert info["demo_license_key"] == generate_demo_license_key()


def test_mcp_server_requires_pro(monkeypatch):
    monkeypatch.delenv("APEX_LICENSE_KEY", raising=False)
    from apex.mcp_server import run_mcp_server

    with pytest.raises(EditionError):
        run_mcp_server()


def test_mcp_server_starts_with_pro_license(monkeypatch):
    key = generate_license_key("demo")
    monkeypatch.setenv("APEX_LICENSE_KEY", key)
    monkeypatch.setenv("APEX_ENTITLEMENT", "demo")

    from unittest.mock import MagicMock, patch

    fake_mcp = MagicMock()
    fake_fastmcp = MagicMock()
    fake_fastmcp.FastMCP.return_value = fake_mcp

    with patch.dict("sys.modules", {"fastmcp": fake_fastmcp}):
        from apex.mcp_server import run_mcp_server

        run_mcp_server()
    fake_mcp.run.assert_called_once_with(transport="stdio")
