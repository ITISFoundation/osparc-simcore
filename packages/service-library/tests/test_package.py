# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)
from servicelib.utils import is_osparc_repo_dir, search_osparc_repo_dir


def test_run_pylint(pylintrc, package_dir):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)


def test_no_pdbs_in_place(package_dir):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=package_dir)


def test_utils(osparc_simcore_root_dir, package_dir):
    assert is_osparc_repo_dir(osparc_simcore_root_dir)

    assert search_osparc_repo_dir(osparc_simcore_root_dir) == osparc_simcore_root_dir

    # assert not search_osparc_repo_dir(package_dir), "package is installed, should not be in osparc-repo"
    # assert search_osparc_repo_dir(package_dir) == osparc_simcore_root_dir, "in develop mode"

    assert not search_osparc_repo_dir(osparc_simcore_root_dir.parent)
