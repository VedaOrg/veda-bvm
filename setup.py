#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import (
    setup,
    find_packages,
)

with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

extras_require = {
    "veda": install_requires,
}

install_requires = extras_require["veda"]

with open("README.md") as readme_file:
    long_description = readme_file.read()

setup(
    name="veda",
    version="0.1.0",
    description="Python implementation of the BVM",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Saital",
    author_email="vedasaital@gmail.com",
    url="https://github.com/VedaOrg/bvm",
    include_package_data=True,
    py_modules=["veda"],
    install_requires=install_requires,
    extras_require=extras_require,
    license="MIT",
    zip_safe=False,
    keywords="bitcoin blockchain bvm",
    packages=find_packages(exclude=["tests", "tests.*", "scripts", "scripts.*"]),
    package_data={"veda": ["py.typed"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.9",
    ],
    entry_points={
        'console_scripts': [
            'veda=veda.main:main',
        ],
    },
)
