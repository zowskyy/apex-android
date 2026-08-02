"""Wrapper launcher inventory."""

from apex.wrappers_info import REPO_ROOT, wrapper_matrix


def test_wrapper_files_exist():
    root = REPO_ROOT
    required = [
        "wrappers/README.md",
        "wrappers/install.sh",
        "wrappers/install.ps1",
        "wrappers/windows/apex-gui.bat",
        "wrappers/windows/apex-mobile.bat",
        "wrappers/linux/apex-gui.sh",
        "wrappers/linux/apex-mobile.sh",
        "wrappers/macos/apex-gui.command",
        "wrappers/macos/apex-mobile.command",
        "wrappers/docker/docker-compose.yml",
        "wrappers/android/build.sh",
    ]
    for relative in required:
        assert (root / relative).is_file(), relative


def test_wrapper_matrix_covers_platforms():
    matrix = wrapper_matrix()
    platforms = {entry["platform"] for entry in matrix.values()}
    assert "Windows" in platforms
    assert "macOS" in platforms
    assert "Linux" in platforms
    assert "Android" in platforms
    assert "iOS" in platforms
    assert "Docker" in platforms
