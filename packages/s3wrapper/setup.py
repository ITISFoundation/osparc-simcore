from setuptools import (
    setup,
    find_packages
)


def load_requirements(requirement_filepath='requirements.txt'):
    requires = []
    with open(requirement_filepath, "r") as fh:
        requires = [line.strip() for line in fh.readlines() if "#" not in line]
    return requires

setup(
    name='s3wrapper',
    version='0.1.0',
    package_dir={"": "src"},
    packages=find_packages("src"),
    # requirements
    install_requires=load_requirements()
)
