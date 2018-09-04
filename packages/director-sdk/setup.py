from setuptools import find_packages, setup


INSTALL_REQUIRES = [
]

TESTS_REQUIRE = [
    'coveralls~=1.3',
    'pylint~=2.0',
    'pytest~=3.6',
    'pytest-cov~=2.5',
    'pytest-docker~=0.6'
    ]


setup(
    name='simcore_director-sdk',
    version="0.1.0",
    description='oSparc Director client service',
    platforms=['POSIX'],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        '': ['.openapi/v1/*']
    },
    entry_points={
        'console_scripts': ['simcore-director-sdk=simcore_director_sdk.__main__:main']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    zip_safe=False,    
)
