#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
import io
import sys
import re
from os.path import join
from pathlib import Path
from setuptools import setup, find_packages

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
COMMENT = re.compile(r'^\s*#')

def list_packages(*parts):
    pkg_names = []
    with io.open(join(CURRENT_DIR, *parts)) as f:
        pkg_names = [line.strip() for line in f.readlines() if not COMMENT.match(line)]
    return pkg_names

with io.open(CURRENT_DIR/'README.rst') as readme_file:
    readme = readme_file.read()

with io.open(CURRENT_DIR/'HISTORY.rst') as history_file:
    history = history_file.read()

# TODO: load from base
requirements = list_packages(CURRENT_DIR, 'requirements', 'base.txt')

setup_requirements = ['pytest-runner', ]

test_requirements = list_packages(CURRENT_DIR, 'tests', 'requirements.txt')

setup(
    name='simcore-service-library',
    version='0.1.0',
    author="Pedro Crespo (pcrespov)",
    description="Core service library for simcore (or servicelib)",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
    long_description=readme + '\n\n' + history,
    license="MIT license",
    install_requires=requirements,
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    include_package_data=True,
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    zip_safe=False
)
