# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pytest_simcore.helpers.utils_pylint import (
    assert_pylint_is_passing,
    assert_no_pdb_in_code,
)


def test_run_pylint(pylintrc, installed_package_dir):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=installed_package_dir)


def test_no_pdbs_in_place(installed_package_dir):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=installed_package_dir)
