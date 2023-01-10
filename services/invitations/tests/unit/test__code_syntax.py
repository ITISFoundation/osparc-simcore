# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pathlib import Path

from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)


def test_run_pylint(pylintrc: Path, installed_package_dir: Path):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=installed_package_dir)


def test_no_pdbs_in_place(project_slug_dir: Path):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=project_slug_dir)
