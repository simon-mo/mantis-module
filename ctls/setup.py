from setuptools import setup

setup(
    name="mantis_ctl",
    version="0.1",
    packages=["mantis_ctl"],
    install_requires=["Click", "structlog", "numpy", "redis"],
)
