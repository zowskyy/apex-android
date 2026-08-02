from __future__ import annotations

import json
from pathlib import Path

from apex.corpus.store import CorpusStore
from apex.permissions.catalog import lookup_permission
from apex.permissions.enrich import enrich_declared, enrich_with_grants
from apex.providers.apksigner import parse_apksigner_output
from apex.providers.preflight import preflight_apk
from apex.providers.registry import get_registry
from apex.workflows import analyze_apk, doctor


def test_doctor_v2_schema():
    report = doctor()
    assert report["schema_version"] == 2
    assert report["apex"] == "1.0.0"
    assert "tools" in report
    assert "capabilities" in report
    assert "jadx" in report["tools"]
    assert "androguard" in report["tools"]


def test_registry_resolves_decompile_auto():
    registry = get_registry()
    provider = registry.resolve("decompile.java", requested="auto")
    assert provider in {"jadx", "androguard", None}


def test_permission_catalog_known_and_unknown():
    known = lookup_permission("android.permission.INTERNET")
    assert known["catalog_status"] == "matched"
    assert known["label"] == "Internet"
    unknown = lookup_permission("com.oem.permission.CUSTOM")
    assert unknown["catalog_status"] == "unknown"


def test_permission_enrichment_declared_only():
    enriched = enrich_declared(["android.permission.CAMERA"])
    assert enriched[0]["declared"] is True
    assert enriched[0]["granted"] is None


def test_permission_granted_state_from_dumpsys():
    dumpsys = "android.permission.CAMERA: granted=true"
    enriched = enrich_with_grants(["android.permission.CAMERA"], dumpsys)
    assert enriched[0]["granted"] is True
    assert enriched[0]["grant_source"] == "adb.dumpsys"


def test_apksigner_output_parser():
    text = """
Signer #1 certificate DN: CN=Test
Verified using v2 scheme (APK Signature Scheme v2): true
Signer #1 certificate SHA-256 digest: ab:cd:ef
Signer #1 certificate SHA-1 digest: 12:34:56
"""
    parsed = parse_apksigner_output(text)
    assert parsed["schemes"]["v2"] is True
    assert parsed["signers"][0]["sha256"] == "ab:cd:ef"


def test_analyze_report_schema_v3(tmp_path: Path):
    from tests.test_workflows import make_apk

    apk = make_apk(tmp_path / "fixture.apk")
    report = analyze_apk(apk, tmp_path / "out")
    assert report["schema_version"] == 3
    assert report["provenance"]
    assert report["resources"]["permissions_enriched"]
    assert "apkanalyzer" in report["benchmarks"]
    saved = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == 3


def test_preflight_detects_dex(tmp_path: Path):
    from tests.test_workflows import make_apk

    apk = make_apk(tmp_path / "fixture.apk")
    result = preflight_apk(apk)
    assert result["dex_count"] == 1


def test_corpus_store_roundtrip(tmp_path: Path):
    store = CorpusStore(tmp_path / "corpus.db")
    device_id = store.upsert_device("emulator-5554", model="test")
    run_id = store.start_sync(device_id, 0)
    store.register_artifact("abc", 123, "/tmp/base.apk")
    store.record_snapshot(run_id, device_id, 0, "com.example", 1, "1.0", "fp", "abc", "/tmp/r.json")
    store.finish_sync(run_id, "ok")
    assert store.has_snapshot(device_id, 0, "com.example", "fp")
    stats = store.stats(device_id=device_id)
    assert stats["package_count"] == 1
