# pylint:disable=wildcard-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
import subprocess
from pathlib import Path

import pytest
from servicelib.utils import is_osparc_repo_dir, search_osparc_repo_dir


@pytest.fixture
def pylintrc(osparc_simcore_root_dir):
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


def test_run_pylint(pylintrc, package_dir):
    AUTODETECT = 0
    cmd = f"pylint --jobs={AUTODETECT} --rcfile {pylintrc} -v {package_dir}".split()
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, _ = pipes.communicate()
    if pipes.returncode != 0:
        print(std_out.decode('utf-8'))
        assert False, "Pylint failed with error, check this test's stdout to fix it"


def test_no_pdbs_in_place(package_dir):
    # TODO: add also test_dir excluding this function!?
    # TODO: it can be commented!
    # TODO: add check on other undesired code strings?!
    MATCH = re.compile(r"pdb.set_trace()")
    EXCLUDE = ["__pycache__", ".git"]
    for root, dirs, files in os.walk(package_dir):
        for name in files:
            if name.endswith(".py"):
                pypth = Path(root) / name
                code = pypth.read_text()
                found = MATCH.findall(code)
                # TODO: should return line number
                assert not found, "pbd.set_trace found in %s" % pypth
        dirs[:] = [d for d in dirs if d not in EXCLUDE]


def test_utils(osparc_simcore_root_dir, package_dir):
    assert is_osparc_repo_dir(osparc_simcore_root_dir)

    assert search_osparc_repo_dir(osparc_simcore_root_dir) == osparc_simcore_root_dir

    # assert not search_osparc_repo_dir(package_dir), "package is installed, should not be in osparc-repo"
    # assert search_osparc_repo_dir(package_dir) == osparc_simcore_root_dir, "in develop mode"

    assert not search_osparc_repo_dir(osparc_simcore_root_dir.parent)
