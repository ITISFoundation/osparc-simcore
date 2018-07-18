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

INSTALL_REQUIRES = list_requirements_in("docker-base.txt")
TESTS_REQUIRE = list_requirements_in("docker-dev.txt")

setup(
    name='simcore-web-server',
    version='0.0.0',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        '': ['../config/*.yaml'] #FIXME: this is still not copied!
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
