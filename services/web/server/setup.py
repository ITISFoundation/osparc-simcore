#pylint: disable=C0103
#pylint: disable=C0111
import os
import sys
import logging

from setuptools import setup

_CDIR = os.path.dirname( sys.argv[0] if __name__ == "__main__" else __file__)

SRC_DIR = os.path.join(_CDIR, "src")

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


def find_packages(*args, **kargs):
    import setuptools
    _LOGGER.info("Loading %s ...", args)
    found = setuptools.find_packages(*args, **kargs)
    _LOGGER.info("Found %s", found)


def load_requirements(fpath=os.path.join(_CDIR,"requirements.txt")):
    _LOGGER.info("Loading %s ...", fpath)
    requires = []
    with open(fpath, "r") as fh:
        requires = [line.strip() for line in fh.readlines() if "#" not in line]
    _LOGGER.info("Found %d packages in %s", len(requires), fpath)
    return requires


if __name__ == "__main__":

    setup(name="simcore-web-server",
          version="0.0.0",
          description="simcore web-server",
          platforms=["POSIX"],  # TODO:check
          package_dir={"": SRC_DIR},
          packages=find_packages(SRC_DIR),
          package_data={
              "": ["static/*.*", ".config/*.yaml"]
          },
          include_package_data=True,
          # requirements
          install_requires=load_requirements(os.path.join(_CDIR,"requirements/production.txt")),
          setup_requires=["pytest-runner"],
          tests_require=load_requirements(os.path.join(_CDIR,"requirements/testing.txt")),
          zip_safe=False  # TODO:check
          )
