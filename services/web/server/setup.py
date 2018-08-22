import sys
import pathlib
from setuptools import (
    setup,
    find_packages
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


# TODO: normalize naming of packages, scripts and modules naming. E.g in this case
#  package name  : simcore-service-webserver
#  import name   : simcore_service_webserver
#  main console script name: simcore-service-webserver
# TODO: document clear guidelines for versioning and compatibility
#
setup(
    name='simcore-web-server',
    version='0.0.0',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    include_package_data=True,
    package_data={
        'config': ['../config/*.yaml'] #FIXME: this is still not copied!??
    },
    entry_points={
        'console_scripts': ['service-web-server=server.__main__:main']},
    python_requires='>=3.6',
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    setup_requires=['pytest-runner']
)
