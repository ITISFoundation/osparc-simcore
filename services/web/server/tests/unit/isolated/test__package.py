# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)
from simcore_service_webserver.cli import main


def test_run_pylint(pylintrc: Path, package_dir: Path):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)


def test_no_pdbs_in_place(package_dir: Path):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=package_dir)


def test_main(here):
    with pytest.raises(SystemExit) as excinfo:
        main("--help".split())

    assert excinfo.value.code == 0
