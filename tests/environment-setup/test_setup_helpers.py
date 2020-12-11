import re
from pathlib import Path
from textwrap import dedent
from typing import List

import pytest

LIBRARY_SPEC_RE = re.compile(r"(^[^#\n-][\w\[,\]]+[-~>=<.\w]*)")
REQUIREMENT_RE = re.compile(r"-r\w(\w.in|.txt)")


# TODO: Under test. Load instead from every setup. Add __main__
# TODO: Build better install_requires lists by reading from referenced files

# - see also how to deal with
#
#  file:../../../packages/postgres-database ???
#

# https://github.com/jazzband/pip-tools/issues/204


def read_reqs(reqs_path: Path, *, reqpaths=None):
    reqpaths = reqpaths or []
    if reqs_path in reqpaths:
        raise Exception("This is a dependency loop")

    reqpaths.append(reqs_path)

    reqs: List[str] = []
    with reqs_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                lib_match = LIBRARY_SPEC_RE.match(line)
                if lib_match:
                    reqs.append(lib_match.group(0))
                elif line.startswith("-r "):
                    ref_path = (reqs_path / line[len("-r ") :]).resolve()
                    reqs.extend(read_reqs(ref_path, reqpaths=reqpaths))
    return reqs


@pytest.fixture
def setup_module_path():
    # parametrzied fixture
    # path to every setup in repo
    pass


@pytest.fixture
def requirements_in_path(tmpdir) -> Path:
    constraints_reqs_path = tmpdir.mkdir("requirements", exists_ok=True).join(
        "constraints.txt"
    )
    constraints_reqs_path.write_text(
        dedent(
            """
        sqlalchemy>=1.3.3                             # https://nvd.nist.gov/vuln/detail/CVE-2019-7164
        sqlalchemy[postgresql_psycopg2binary]>=1.3.3  # https://nvd.nist.gov/vuln/detail/CVE-2019-7164
        pyyaml>=5.3                                   # Vulnerable
        urllib3>=1.25.8                               # Vulnerability
    """
        )
    )

    pg_reqs_path = tmpdir.mkdir(
        "packages", "postgres-database", "requirements", exists_ok=True
    ).join("_base.in")
    pg_reqs_path.write_text(
        dedent(
            """
        -c ../../../requirements/constraints.txt

        git+https://github.com/ITISFoundation/osparc-simcore.git@c8669fb52659b684514fefa4f3b4599f57f276a0#egg=simcore-service-library&subdirectory=packages/service-library  # via -r requirements/_base.txt

        sqlalchemy[postgresql_psycopg2binary]
        yarl
    """
        )
    )

    requirements_path = tmpdir.mkdir(
        "services", "catalog", "requirements", exists_ok=True
    ).join("_base.in")
    requirements_path.write_text(
        dedent(
            """
    -c ../../../requirements/constraints.txt
    -r ../../../packages/postgres-database/requirements/_base.in


    # fastapi and extensions
    fastapi[all]
    async-exit-stack  # not needed when python>=3.7
    async-generator   # not needed when python>=3.7

    """
        )
    )
    return requirements_path


def test_read_requirements(requirements_in_path):

    requirements = read_reqs(requirements_in_path)
    print(requirements)
