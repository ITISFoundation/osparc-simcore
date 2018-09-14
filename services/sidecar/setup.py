# -*- coding: utf-8 -*-
import sys
import pathlib

from setuptools import (
    find_packages,
    setup,
)

_CDIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent
_PACKAGES_DIR = _CDIR.absolute().parent.parent / "packages"

def list_requirements_in(filename):
    requires = []
    with (_CDIR / "requirements" / filename).open() as fh:
        requires = [line.strip() for line in fh.readlines() if not line.lstrip().startswith("#")]
    return requires


INSTALL_REQUIRES = list_requirements_in("base.txt")

# FIXME: not sure how to add these dependencies *here* and *only* in production. Now using requirements/prod.txt
SC_PACKAGES = [
    "s3wrapper",
    "simcore-sdk"
]

setup(
    name='simcore-service-sidecar',
    version='0.0.1',
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    install_requires=INSTALL_REQUIRES,
    python_requires='>=3.6',
)
