from setuptools import find_packages, setup


INSTALL_REQUIRES = [
    'docker==3.5.0',
    'tenacity==4.12.0',
    'aiohttp==3.3.2',
    'aiohttp_apiset==0.9.3',
    'requests==2.19.1',
]

TESTS_REQUIRE = [
    'coveralls~=1.3',
    'pylint~=2.0',
    'pytest-aiohttp',
    'pytest~=3.6',
    'pytest-cov~=2.5',
    'pytest-docker~=0.6'
    ]


setup(
    name='simcore-service-director',
    version="0.1.0",
    description='oSparc Director webserver service',
    platforms=['POSIX'],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        '': ['.openapi/v1/*']
    },
    entry_points={
        'console_scripts': ['simcore-service-director=simcore_service_director.__main__:main']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    zip_safe=False,
)
