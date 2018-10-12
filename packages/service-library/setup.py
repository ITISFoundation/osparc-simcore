#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

# TODO: load from base
requirements = [
    'aiohttp',
    'openapi-core',
    'werkzeug',
    'pyyaml'
    ]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', ]

setup(
    name='simcore-service-library',
    version='0.1.0',
    author="Pedro Crespo",
    description="Core service library for simcore",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
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
