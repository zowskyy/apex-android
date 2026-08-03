"""Guard Chaquopy pip manifest and document the desktop-vs-Android test gap.

Desktop CI runs pytest with pip install -e ".[dev]" which pulls full transitive
deps automatically. The Android APK uses Chaquopy pip with --no-deps, so missing
packages only show up at runtime unless scripts/smoke_android_engine_imports.sh
runs after assembleRelease (wired into build_standalone.sh + CI).
"""

from pathlib import Path


def test_android_chaquopy_lists_transitive_python_deps():
    gradle = Path("wrappers/android/standalone/app/build.gradle").read_text(encoding="utf-8").lower()
    required = [
        "markupsafe",  # jinja2 (workflows.py)
        "jinja2",
        "cffi",  # cryptography
        "pycparser",
        "loguru",
        "androguard",
    ]
    missing = [pkg for pkg in required if pkg not in gradle]
    assert not missing, f"build.gradle missing Chaquopy pip installs: {missing}"


def test_android_vendored_mutf8_for_chaquopy():
    """mutf8 has no Chaquopy wheel; pure-Python copy lives in src/main/python."""
    base = Path("wrappers/android/standalone/app/src/main/python/mutf8")
    assert (base / "__init__.py").is_file()
    assert (base / "mutf8.py").is_file()
