# pylint: disable=missing-docstring
from setuptools import setup

setup(
    name="raylab",
    version="0.3.1",
    py_modules=["raylab"],
    install_requires=[
        "Click",
        "matplotlib",
        "numpy",
        "pandas",
        "seaborn",
        "requests",
        "ray",
        "gym",
    ],
    entry_points="""
        [console_scripts]
        raylab=raylab.cli:cli
        viskit=raylab.viskit.plot:cli
    """,
)
