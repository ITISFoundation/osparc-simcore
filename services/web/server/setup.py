import pathlib
import sys
import re
from os.path import join
import io
from setuptools import (
    find_packages,
    setup
)

_CDIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent

def list_packages(*parts):
    pkg_names = []
    COMMENT = re.compile(r'^\s*#')
    with io.open(join(_CDIR, *parts)) as f:
        pkg_names = [line.strip() for line in f.readlines() if not COMMENT.match(line)]
    return pkg_names

#-----------------------------------------------------------------

INSTALL_REQUIRES = list_packages("requirements", "base.txt")
TESTS_REQUIRE = list_packages("tests", "requirements.txt")


setup(
    name='simcore-service-webserver',
    version="0.1.0",
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    include_package_data=True,
    package_data={
        '': [
            'config/*.y*ml',
            'data/*.json',
            'templates/**/*.html',
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
