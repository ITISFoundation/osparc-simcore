# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
from pathlib import Path

import pytest

from pytest_simcore.helpers.utils_pylint import assert_pylint_is_passing


@pytest.fixture
def pylintrc(osparc_simcore_root_dir: Path) -> Path:
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


def test_run_pylint(pylintrc, installed_package_dir):
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=installed_package_dir)


def test_no_pdbs_in_place(installed_package_dir):
    MATCH = re.compile(r"pdb.set_trace()")
    EXCLUDE = ["__pycache__", ".git"]
    for root, dirs, files in os.walk(installed_package_dir):
        for name in files:
            if name.endswith(".py"):
                pypth = Path(root) / name
                code = pypth.read_text()
                found = MATCH.findall(code)
                assert not found, "pbd.set_trace found in %s" % pypth
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
