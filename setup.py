from setuptools import setup, find_packages
setup(
    name="apex-android",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["jinja2>=3.1.0"],
    entry_points={"console_scripts": ["apex=apex:main"]},
    python_requires=">=3.9",
)
