"""Code Pilot and shared tool registry tests."""

import pytest

from apex.agent import run_code_pilot
from apex.agent.providers import HeuristicProvider
from apex.edition import EditionError, generate_license_key
from apex.tools import call_tool, list_tools


@pytest.fixture()
def pro_license(monkeypatch):
    key = generate_license_key("demo")
    monkeypatch.setenv("APEX_LICENSE_KEY", key)
    monkeypatch.setenv("APEX_ENTITLEMENT", "demo")


def test_tool_registry_lists_core_tools():
    names = {item["name"] for item in list_tools()}
    assert {"inspect", "security_scan", "decompile", "doctor"} <= names


def test_call_tool_doctor():
    result = call_tool("doctor")
    assert "apex" in result
    assert "ready" in result


def test_code_pilot_requires_pro():
    with pytest.raises(EditionError):
        run_code_pilot("doctor", provider=HeuristicProvider())


def test_code_pilot_heuristic_doctor(pro_license):
    result = run_code_pilot("is the engine ready? doctor", provider=HeuristicProvider())
    assert result["provider"] == "heuristic"
    assert result["trace"]
    assert result["trace"][0]["tool"] == "doctor"
    assert "answer" in result


def test_code_pilot_cli_help(pro_license, monkeypatch):
    monkeypatch.setenv("APEX_DISCLAIMER_ACCEPTED", "1")
    from apex.cli import main

    assert main(["agent"]) == 1
