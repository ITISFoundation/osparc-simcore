#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
from pathlib import Path
from setuptools import setup, find_packages

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
comment_pattern = re.compile(r'^\s*#')

def list_packages(fpath: Path):
    with fpath.open() as f:
        return [line.strip() for line in f.readlines() if not comment_pattern.match(line)]

readme = (current_dir/'README.rst').read_text()
history = (current_dir/'HISTORY.rst').read_text()

install_requirements = [
    'aiohttp==3.4.4',
    'aiohttp_session==2.7.0', # FIXME: should go, since not all service might have sessions
    'aiopg==0.15.0',          # chosen asyncio client tool to interact with postgres
    'attr==0.3.1',
    'cryptography==2.4.2',
    'openapi_core==0.7.1',
    'psycopg2==2.7.6.1',
    'SQLAlchemy==1.2.15',
    'typing==3.6.6',
    'Werkzeug==0.14.1',
    'PyYAML==3.13',
    'yarl==1.3.0',
]
test_requirements = list_packages(current_dir/ "requirements" / "tests.txt")
setup_requirements = ['pytest-runner', ]


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
    zip_safe=False
)
