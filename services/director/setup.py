import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

if sys.version_info<(3, 6):
    raise RuntimeError("Requires >=3.6, got %s. Did you forget to activate virtualenv?" % sys.version_info)


def read_reqs( reqs_path: Path):
    reqs =  re.findall(r'(^[^#-][\w]+[-~>=<.\w]+)', reqs_path.read_text(), re.MULTILINE)
    # TODO: temporary excluding requirements using git
    # https://pip.pypa.io/en/stable/reference/pip_install/#vcs-support
    return [r for r in reqs if not r.startswith('git')]


install_requirements = read_reqs( here / "requirements" / "_base.txt" ) + [
    "aiohttp-apiset==0.0.0.dev0",
    "simcore-service-library==0.1.0"
]

test_requirements = read_reqs( here / "requirements" / "_test.txt" )



_CONFIG = dict(
    name='simcore-service-director',
    version='0.1.0',
    description='oSparc Director webserver service',
    author='Sylvain Anderegg (sanderegg)',
    python_requires='>=3.6',
    packages=find_packages(where='src'),
    package_dir={
        '': 'src',
    },
    include_package_data=True,
    install_requires= install_requirements,
    tests_require=test_requirements,
    setup_requires=['pytest-runner'],
    package_data={
        '': [
            'oas3/**/*.yaml',
            'oas3/**/schemas/*.json',
            'oas3/**/schemas/*.yaml',
            ],
    },
    entry_points={
        'console_scripts': [
            'simcore-service-director = simcore_service_director.__main__:main',
        ],
    },
)

def main():
    """ Execute the setup commands.
     """
    setup(**_CONFIG)
    return 0 # syccessful termination

if __name__ == "__main__":
    raise SystemExit(main())
