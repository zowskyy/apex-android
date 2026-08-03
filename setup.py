from pathlib import Path

from setuptools import find_packages, setup


def _version() -> str:
    for line in Path("apex/version.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("apex/version.py is missing __version__")


setup(
    name="apex-android",
    version=_version(),
    description="Secure Android package inspection, decompilation, and rebuilding",
    packages=find_packages(),
    install_requires=[
        "androguard>=4.1.4",
        "jinja2>=3.1.0",
    ],
    extras_require={
        "mcp": ["fastmcp>=2.0"],
        "postgres": ["psycopg[binary]>=3.0"],
        "dev": [
            "pytest>=8.0",
            "pytest-benchmark>=4.0",
            "ruff>=0.16.1",
            "fastmcp>=2.0",
        ],
    },
    entry_points={"console_scripts": ["apex=apex:main"]},
    python_requires=">=3.10",
)
