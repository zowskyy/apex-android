from setuptools import find_packages, setup

setup(
    name="apex-android",
    version="1.0.0",
    description="Secure Android package inspection, decompilation, and rebuilding",
    packages=find_packages(),
    package_data={"apex": ["data/permissions.json", "data/trackers.json"]},
    install_requires=[
        "androguard>=4.1.4",
        "jinja2>=3.1.0",
    ],
    entry_points={"console_scripts": ["apex=apex:main"]},
    python_requires=">=3.10",
)
