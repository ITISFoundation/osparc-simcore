from setuptools import (
    setup,
    find_packages
)

INSTALL_REQUIRES = [
    'networkx==2.1',
    'psycopg2-binary==2.7.4',
    'sqlalchemy==1.2.9',
    'tenacity==4.12.0',
    'trafaret-config==2.0.1',
    'aiofiles~=0.4',
    'aiohttp~=3.3'
]

TEST_REQUIRE = [
    'coveralls~=1.3',
    'mock~=2.0',
    'pylint~=2.0',
    'pytest~=3.6',
    'pytest-asyncio~=0.9',
    'pytest-cov~=2.5',
    'pytest-docker~=0.6',
    'requests~=2.19',
    'docker~=3.5'
]

setup(
    name='simcore-sdk',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    python_requires='>=3.6',
    install_requires=INSTALL_REQUIRES,
    tests_require=TEST_REQUIRE,
    extras_require= {
        'test': TEST_REQUIRE
    },
    setup_requires=['pytest-runner']
)
