# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from pytest_simcore.helpers.utils_pylint import assert_pylint_is_passing


@pytest.fixture
def pylintrc(osparc_simcore_root_dir):
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


def test_run_pylint(pylintrc, package_dir):
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)
