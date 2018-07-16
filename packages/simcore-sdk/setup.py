from setuptools import (
    setup,
    find_packages
)

def load_requirements(requirement_filepath='requirements.txt'):
    requires = []
    with open(requirement_filepath, "r") as fh:
        requires = [line.strip() for line in fh.readlines() if "#" not in line]
    return requires

test_deps=load_requirements("requirements/testing.txt")

setup(
    name='simcore-sdk',
    version='0.1.0',
    package_dir={"": "src"},
    packages=find_packages("src"),
    # requirements
    install_requires=load_requirements("requirements/production.txt"),
    tests_require=test_deps,
    extras_require= {
        'test': test_deps
    },
    setup_requires=["pytest-runner"]
)
