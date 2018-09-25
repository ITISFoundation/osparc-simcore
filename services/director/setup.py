import pathlib
import sys

from setuptools import find_packages, setup

_CDIR = pathlib.Path(sys.argv[0] if __name__ == '__main__' else __file__).parent
_PACKAGES_DIR = _CDIR.absolute().parent.parent / 'packages'

def list_requirements_in(filename):
    requires = []
    with (_CDIR / 'requirements' / filename).open() as fh:
        requires = [line.strip() for line in fh.readlines() if not line.lstrip().startswith('#')]
    return requires

def package_files(package_dir, data_dir):
    abs_path = _CDIR / package_dir / data_dir
    return [str(p.relative_to(_CDIR / package_dir)) for p in abs_path.rglob('**/*.*')]


INSTALL_REQUIRES = list_requirements_in('base.txt')
TESTS_REQUIRE = list_requirements_in('test.txt')
PACKAGES = find_packages(where='src')
EXTRA_FILES = package_files('src/simcore_service_director', 'oas3')

setup(
    name='simcore-service-director',
    version='0.1.0',
    description='oSparc Director webserver service',
    platforms=['POSIX'],
    package_dir={'': 'src'},
    packages=PACKAGES,
    package_data={
        '': EXTRA_FILES
    },
    entry_points={
        'console_scripts': ['simcore-service-director=simcore_service_director.__main__:main']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require= {
        'test': TESTS_REQUIRE
    },
    zip_safe=False,
    python_requires='>=3.6',
)
