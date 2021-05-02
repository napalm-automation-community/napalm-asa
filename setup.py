"""setup.py file."""

from setuptools import setup, find_packages

__author__ = "Diogo Assumpcao"

with open("requirements.txt", "r") as fs:
    reqs = [r for r in fs.read().splitlines() if (len(r) > 0 and not r.startswith("#"))]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="napalm-asa",
    version="0.1.4",
    packages=find_packages(),
    author="Diogo Assumpcao",
    author_email="daa@hey.com",
    description="Cisco ASA driver for NAPALM",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Topic :: Utilities",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    url="https://github.com/napalm-automation-community/napalm-asa",
    include_package_data=True,
    install_requires=reqs,
)
