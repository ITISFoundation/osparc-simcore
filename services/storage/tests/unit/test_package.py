# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)


def test_run_pylint(pylintrc, package_dir):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)


def test_no_pdbs_in_place(package_dir):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=package_dir)
