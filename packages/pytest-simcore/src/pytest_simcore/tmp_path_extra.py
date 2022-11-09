# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""
    Extends temp_path fixture
        https://docs.pytest.org/en/6.2.x/tmpdir.html#the-tmp-path-fixture

    NOTE: use tmp_path instead of tmpdir
    NOTE: default base temporary directory can be set as `pytest --basetemp=mydir`

"""
from pathlib import Path

import pytest
from pytest import FixtureRequest, TempPathFactory


@pytest.fixture(scope="module")
def temp_folder(request: FixtureRequest, tmp_path_factory: TempPathFactory) -> Path:
    """Module scoped temporary folder"""
    prefix = __name__.replace(".", "_")
    return tmp_path_factory.mktemp(
        basename=f"{prefix}_temp_folder_{request.module.__name__}", numbered=True
    )
