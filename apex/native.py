from __future__ import annotations

from importlib import import_module
from types import ModuleType


def _load(module_name: str, build_dir: str) -> ModuleType:
    try:
        return import_module(module_name)
    except Exception as exc:  # pragma: no cover - depends on local native build state.
        raise RuntimeError(
            f"{module_name} is not installed. Build it with:\n"
            f"  source .venv/bin/activate\n"
            f"  cd {build_dir} && maturin develop --release"
        ) from exc


def zip_reader() -> ModuleType:
    return _load("apex_zip_reader", "core/zip_reader")


def arsc_parser() -> ModuleType:
    return _load("apex_arsc_parser", "core/arsc_parser")


def dex_parser() -> ModuleType:
    return _load("apex_dex_parser", "core/dex_parser")
