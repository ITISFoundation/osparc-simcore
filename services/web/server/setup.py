#pylint: disable=C0103
#pylint: disable=C0111
import logging

from setuptools import find_packages, setup

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def load_requirements(fpath='requirements.txt'):
    requires = []
    with open(fpath, "r") as fh:
        requires = [line.strip() for line in fh.readlines() if "#" not in line]
    _LOGGER.info("Found %d packages in %s", len(requires), fpath)
    return requires


if __name__ == "__main__":

    setup(name="web-server",
          version="0.0.0",
          description="simcore web-server",
          platforms=["POSIX"],  # TODO:check
          package_dir={"": "src"},
          packages=find_packages("src"),
          package_data={
              "": ["static/*.*", ".config/*.*", "mock/*.*"]
          },
          include_package_data=True,
          # requirements
          install_requires=load_requirements("requirements/production.txt"),
          setup_requires=["pytest-runner"],
          tests_require=load_requirements("requirements/testing.txt"),
          zip_safe=False  # TODO:check
          )
