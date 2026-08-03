"""Tests for the native apex_dex_reader Rust extension."""

from pathlib import Path

import pytest

from apex.analysis import dex_metadata

FIXTURE_DEX = Path("core/dex_parser/tests/fixtures/classes.dex")


@pytest.fixture()
def native_dex():
    try:
        import apex_dex_reader
    except ImportError:
        pytest.skip("apex_dex_reader extension not built")
    return apex_dex_reader


def test_native_dex_metadata_matches_fixture(native_dex):
    raw = FIXTURE_DEX.read_bytes()
    metadata = dict(native_dex.dex_metadata(raw, "classes.dex"))

    assert metadata["dex"] == "classes.dex"
    assert len(metadata["classes"]) == 7
    assert any(cls["name"] == "com.apex.testapp.MainActivity" for cls in metadata["classes"])
    assert any(method["name"] == "onCreate" for method in metadata["methods"])
    assert any(edge["caller_method"] == "onCreate" for edge in metadata["edges"])


def test_analysis_prefers_native_dex(native_dex):
    raw = FIXTURE_DEX.read_bytes()
    metadata = dex_metadata(raw, "classes.dex")
    assert len(metadata["classes"]) == 7
    assert any(method["name"] == "onCreate" for method in metadata["methods"])


def test_native_decode_method_oncreate(native_dex):
    raw = FIXTURE_DEX.read_bytes()
    metadata = dict(native_dex.dex_metadata(raw, "classes.dex"))
    on_create = next(method for method in metadata["methods"] if method["name"] == "onCreate")
    assert on_create["instruction_count"] == 4
    assert on_create["code_off"] > 0

    decoded = dict(native_dex.decode_method(raw, on_create["code_off"]))
    assert decoded["insns_size"] == 9  # total 16-bit code units for 4 instructions
    assert len(decoded["instructions"]) == 4
    assert decoded["instructions"][0]["opcode"] == 0x6f  # invoke-super
