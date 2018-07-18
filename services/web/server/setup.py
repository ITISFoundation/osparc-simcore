import sys
import os
from setuptools import (
    setup,
    find_packages
)

_CDIR = os.path.dirname( sys.argv[0] if __name__ == "__main__" else __file__)

INSTALL_REQUIRES = [
    'aiohttp==3.3.2',
    'aiohttp-security==0.2.0',
    'aiohttp_session[secure]==2.5.1',
    'aiohttp-swagger==1.0.5',
    'aiopg[sa]==0.14.0',
    'aio-pika==2.9.0',
    'celery==4.1.0',
    'kombu==4.1.0',
    'minio==4.0.0',
    'networkx==2.1',
    'passlib==1.7.1',
    'psycopg2==2.7.4',
    'python-socketio==1.9.0',
    'requests==2.19.0',
    'sqlalchemy==1.2.8',
    'tenacity==4.12.0',
    'trafaret-config==2.0.1'
]

TESTS_REQUIRE = [
    'coveralls~=1.3',
    'mock~=2.0',
    'passlib',
    'pylint~=2.0',
    'pytest~=3.6',
    'pytest-cov~=2.5',
    'pytest-docker~=0.6'
]

setup(
    name='simcore-web-server',
    version='0.0.0',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        "": ["static/*.*", ".config/*.yaml"]
    },
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    setup_requires=['pytest-runner']
)
