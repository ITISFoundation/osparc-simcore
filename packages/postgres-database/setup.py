import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
readme = Path( here / "README.md" ).read_text()
version = Path(here/ "VERSION").read_text().strip()

def read_reqs( reqs_path: Path):
    return re.findall(r'(^[^#-][\w]+[-~>=<.\w]+)', reqs_path.read_text(), re.MULTILINE)

# Weak dependencies
install_requirements = read_reqs( here / "requirements" / "_base.in" )

# Strong dependencies
migration_requirements = read_reqs( here / "requirements" / "_migration.txt" )
test_requirements = read_reqs( here / "requirements" / "_test.txt" )


setup(
    name='simcore-postgres-database',
    version=version,
    author="Pedro Crespo (pcrespov)",
    description="Database models served by the simcore 'postgres' core service",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
    long_description=readme,
    license="MIT license",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    test_suite='tests',
    install_requires=install_requirements,
    tests_require=test_requirements,
    extras_require= {
        'migration': migration_requirements,
        'test': test_requirements
    },
    include_package_data=True,
    package_data={
        '': [
            '*.ini',
            'migration/*.py',
            'migration/*.mako',
            'migration/versions/*.py',
         ]
    },
    entry_points = {
        'console_scripts': [
            'simcore-postgres-database=simcore_postgres_database.cli:main',
            'sc-pg=simcore_postgres_database.cli:main',
        ]
    },
    zip_safe=False
)
