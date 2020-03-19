
import os
from setuptools import setup

setup(
    name='pytest-simcore',
    version='0.1.0',
    maintainer='pcrespov',
    maintainer='sanderegg'
    description='pytest plugin with fixtures and test helpers for osparc-simcore repo modules',
    py_modules=['pytest_simcore'],
    python_requires='>=3.6.*',
    install_requires=[
        'pytest>=3.5.0',
        "aio_pika",
        "aiohttp",
        "aioredis",
        "celery",
        "docker_py",
        "gevent_socketio",
        "PyYAML",
        "SQLAlchemy",
        "tenacity",
        "yarl",
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'simcore = pytest_simcore',
        ],
    },
)
