"""pytest-benchmark guards for native ZIP/DEX readers."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

import apex

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_test_apk  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def realistic_apk() -> Path:
    path = FIXTURES / "sample_test.apk"
    if not path.is_file():
        generate_test_apk.build_apk(path)
    return path


@pytest.mark.benchmark(group="zip_reader")
@pytest.mark.skipif(apex._native_zip is None, reason="apex_zip_reader not installed")
def test_bench_native_extract_apk(benchmark, realistic_apk: Path, tmp_path: Path) -> None:
    work = tmp_path / "bench_native"

    def run() -> int:
        if work.exists():
            import shutil

            shutil.rmtree(work)
        extract_dir, report = apex.extract_apk(realistic_apk, work)
        return int(report.get("extracted") or 0)

    count = benchmark(run)
    assert count > 0


@pytest.mark.benchmark(group="zip_reader")
def test_bench_python_zip_inventory(benchmark, realistic_apk: Path) -> None:
    def run() -> int:
        with zipfile.ZipFile(realistic_apk) as zf:
            return len(zf.namelist())

    count = benchmark(run)
    assert count > 100


@pytest.mark.benchmark(group="dex_reader")
@pytest.mark.skipif(apex._native_dex is None, reason="apex_dex_reader not installed")
def test_bench_native_dex_metadata(benchmark, realistic_apk: Path) -> None:
    with zipfile.ZipFile(realistic_apk) as zf:
        dex = zf.read("classes.dex")

    def run() -> int:
        meta = apex._native_dex.metadata(dex, "classes.dex")
        return len(meta.get("classes") or [])

    count = benchmark(run)
    assert count >= 0
