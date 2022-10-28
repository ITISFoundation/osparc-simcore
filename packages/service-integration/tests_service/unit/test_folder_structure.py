# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import pytest
from service_integration.pytest_plugin.folder_structure import (
    assert_path_in_repo,
    get_expected_files,
)


@pytest.mark.parametrize(
    "expected_path", get_expected_files("{{ cookiecutter.docker_base.split(':')[0] }}")
)
def test_path_in_repo(expected_path: str, project_slug_dir: Path):
    assert_path_in_repo(expected_path, project_slug_dir)
