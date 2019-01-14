#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
from pathlib import Path
from setuptools import setup, find_packages

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
comment_pattern = re.compile(r'^\s*#')


readme = (current_dir/'README.rst').read_text()
history = (current_dir/'HISTORY.rst').read_text()

install_requirements = [
    'aiohttp',
    'aiohttp_session', # FIXME: should go, since not all service might have sessions
    'aiopg',           # chosen asyncio client tool to interact with postgres
    'cryptography',
    'openapi_core',
    'psycopg2',
    'SQLAlchemy',
    'typing',
    'Werkzeug',
    'pyyaml>=4.2b1', # https://nvd.nist.gov/vuln/detail/CVE-2017-18342
    'yarl',
]

test_requirements = [
    'pytest',
    'pytest-aiohttp', 'pytest-cov',
]

setup_requirements = [
    'pytest-runner',
]


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
    install_requires=install_requirements,
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    include_package_data=True,
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require={
        'test': test_requirements
    },
    zip_safe=False
)
