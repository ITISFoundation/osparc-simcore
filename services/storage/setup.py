import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

if sys.version_info < (3, 6):
    raise RuntimeError("Requires 3.6, got %s. Did you forget to activate virtualenv?" % sys.version_info)


def read_reqs( reqs_path: Path):
    return re.findall(r'(^[^#-][\w]+[-~>=<.\w]+)', reqs_path.read_text(), re.MULTILINE)


install_requirements = read_reqs( here / "requirements" / "_base.txt" ) + [
    "s3wrapper==0.1.0",
    "simcore-sdk==0.1.0",
    "simcore-service-library==0.1.0"
]

test_requirements = read_reqs( here / "requirements" / "_test.txt" )


setup_config = dict(
    name='simcore-service-storage',
    version='0.1.0',
    description='Service to manage data storage in simcore',
    author='Manuel Guidon (mguidon)',
    python_requires='>3.6, <3.7',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires= install_requirements,
    tests_require=test_requirements,
    package_data={
        '': [
            'data/*.json',
            'data/*.yml',
            'data/*.yaml'
            ],
    },
    entry_points={
        'console_scripts': [
            'simcore-service-storage = simcore_service_storage.cli:main',
        ],
    },
)


def main():
    """ Execute the setup commands

    """
    setup(**setup_config)
    return 0 # syccessful termination

if __name__ == "__main__":
    raise SystemExit(main())
