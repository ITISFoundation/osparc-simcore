# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from servicelib.utils import is_osparc_repo_dir, search_osparc_repo_dir


def test_utils(osparc_simcore_root_dir, package_dir):
    assert is_osparc_repo_dir(osparc_simcore_root_dir)

    assert search_osparc_repo_dir(osparc_simcore_root_dir) == osparc_simcore_root_dir

    # assert not search_osparc_repo_dir(package_dir), "package is installed, should not be in osparc-repo"
    # assert search_osparc_repo_dir(package_dir) == osparc_simcore_root_dir, "in develop mode"

    assert not search_osparc_repo_dir(osparc_simcore_root_dir.parent)
