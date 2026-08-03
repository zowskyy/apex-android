"""Guard Chaquopy pip manifest — missing transitive deps break on-device import."""

from pathlib import Path


def test_android_chaquopy_lists_transitive_python_deps():
    gradle = Path("wrappers/android/standalone/app/build.gradle").read_text(encoding="utf-8").lower()
    required = [
        "markupsafe",  # jinja2 (workflows.py)
        "jinja2",
        "cffi",  # cryptography
        "pycparser",
        "mutf8",  # androguard dex
        "loguru",
        "androguard",
    ]
    missing = [pkg for pkg in required if pkg not in gradle]
    assert not missing, f"build.gradle missing Chaquopy pip installs: {missing}"
