from setuptools import setup

setup(
    name="mantis",
    version="0.1",
    packages=["mantis"],
    install_requires=["Click"],
    entry_points="""
        [console_scripts]
        mantis=mantis:wrapper
    """,
)
