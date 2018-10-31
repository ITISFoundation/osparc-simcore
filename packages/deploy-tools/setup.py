#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script

"""
import sys
import re
from pathlib import Path
from setuptools import setup, find_packages
from typing import List

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
COMMENT = re.compile(r'^\s*#')

def list_packages(reqpath: Path) -> List[str]:
    pkg_names = []
    with reqpath.open() as f:
        pkg_names = [line.strip() for line in f.readlines() if not COMMENT.match(line)]
    return pkg_names


requirements = list_packages(CURRENT_DIR / 'requirements.txt')

setup_requirements = ['pytest-runner', ]

test_requirements = list_packages(CURRENT_DIR / 'tests' / 'requirements.txt')

setup(
    name='simcore-deploy-tools',
    version='0.1.0',
    author="Pedro Crespo (pcrespov)",
    description="Collection of deploy tools",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6'
    ],
    license="MIT license",
    install_requires=requirements,
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    python_requires='>3.6, <3.7',
    include_package_data=True,
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'simcore-deploy-tools = deploytools.cli:main',
        ],
    }
)
