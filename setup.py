from setuptools import setup, find_packages

setup(
    name="apex-android",
    version="0.2.0",
    description="Secure Android package inspection, decompilation, and rebuilding",
    packages=find_packages(),
    install_requires=[
        "androguard>=4.1.4",
        "jinja2>=3.1.0",
        "networkx>=3.0",
    ],
    entry_points={"console_scripts": ["apex=apex:main"]},
    python_requires=">=3.10",
)
