import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs( reqs_path: Path):
    return re.findall(r'(^[^#-][\w]+[-~>=<.\w]+)', reqs_path.read_text(), re.MULTILINE)


install_requirements = read_reqs( here / "requirements" / "_base.txt" ) + [
    "s3wrapper==0.1.0",
    "simcore-sdk==0.1.0",
    "simcore-service-storage-sdk==0.1.0"
]

test_requirements = read_reqs( here / "requirements" / "_test.txt" )


setup(
    name='simcore-service-sidecar',
    version='0.0.1',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=install_requirements,
    python_requires='>=3.6',
    test_suite='tests',
    tests_require=test_requirements
)
