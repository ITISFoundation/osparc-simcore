import pathlib
import sys

from setuptools import (
    find_packages,
    setup
)

_CDIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent

def list_requirements_in(filename):
    requires = []
    with (_CDIR / "requirements" / filename).open() as fh:
        requires = [line.strip() for line in fh.readlines() if not line.lstrip().startswith("#")]
    return requires


#####################################################################################
# NOTE see https://packaging.python.org/discussions/install-requires-vs-requirements/

INSTALL_REQUIRES = list_requirements_in("base.txt")
TESTS_REQUIRE = list_requirements_in("tests.txt")


setup(
    name='simcore-service-webserver',
    version="0.0.2",
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    include_package_data=True,
    package_data={
        '': [
            'config/*.yaml',
            'oas3/v1/*.yaml'
            ]
    },
    entry_points={
        'console_scripts': [
            'simcore-service-webserver=simcore_service_webserver.__main__:main', ]
        },
    python_requires='>=3.6',
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    setup_requires=['pytest-runner']
)
