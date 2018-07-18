from setuptools import setup

install_requires = [
    'networkx==2.1',
    'psycopg2==2.7.4',
    'sqlalchemy==1.2.8',
    'tenacity==4.12.0'
]

tests_require = [
    'coveralls~=1.3',
    'mock~=2.0',
    'pylint~=2.0',
    'pytest~=3.6',
    'pytest-cov~=2.5',
    'pytest-docker~=0.6',
    'requests~=2.19'
]

setup(
    name='simcore-sdk',
    version='0.1.0',
    package_dir={'': 'src'},
    packages=['simcore_sdk'],
    python_requires='>=3.6',
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require= {
        'test': tests_require
    },
    setup_requires=['pytest-runner']
)
