# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
from faker import Faker
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_efs_guardian.core.settings import AwsEfsSettings
from simcore_service_efs_guardian.services.efs_manager import (
    EfsManager,
    NodeID,
    ProjectID,
)

pytest_simcore_core_services_selection = ["rabbit"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


@pytest.fixture
async def cleanup(app: FastAPI):

    yield

    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS
    _dir_path = Path(aws_efs_settings.EFS_MOUNTED_PATH)
    if Path.exists(_dir_path):
        for root, dirs, files in os.walk(_dir_path):
            for name in dirs + files:
                file_path = os.path.join(root, name)
                # Get the current permissions of the file or directory
                current_permissions = os.stat(file_path).st_mode
                # Add write permission for the owner (user)
                os.chmod(file_path, current_permissions | stat.S_IWUSR)

        shutil.rmtree(_dir_path)


def assert_permissions(
    file_path: Path,
    expected_readable: bool,
    expected_writable: bool,
    expected_executable: bool,
):
    file_stat = os.stat(file_path)
    file_permissions = file_stat.st_mode
    is_readable = bool(file_permissions & stat.S_IRUSR)
    is_writable = bool(file_permissions & stat.S_IWUSR)
    is_executable = bool(file_permissions & stat.S_IXUSR)

    assert (
        is_readable == expected_readable
    ), f"Expected readable={expected_readable}, but got readable={is_readable} for {file_path}"
    assert (
        is_writable == expected_writable
    ), f"Expected writable={expected_writable}, but got writable={is_writable} for {file_path}"
    assert (
        is_executable == expected_executable
    ), f"Expected executable={expected_executable}, but got executable={is_executable} for {file_path}"


async def test_remove_write_access_rights(
    faker: Faker,
    mocked_redis_server: None,
    app: FastAPI,
    cleanup: None,
):
    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS

    _project_id = ProjectID(faker.uuid4())
    _node_id = NodeID(faker.uuid4())
    _storage_directory_name = faker.word()
    _dir_path = (
        aws_efs_settings.EFS_MOUNTED_PATH
        / aws_efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY
        / f"{_project_id}"
        / f"{_node_id}"
        / f"{_storage_directory_name}"
    )

    efs_manager: EfsManager = app.state.efs_manager

    with patch(
        "simcore_service_efs_guardian.services.efs_manager.os.chown"
    ) as mocked_chown:
        await efs_manager.create_project_specific_data_dir(
            project_id=_project_id,
            node_id=_node_id,
            storage_directory_name=_storage_directory_name,
        )

    size_before = await efs_manager.get_project_node_data_size(
        project_id=_project_id, node_id=_node_id
    )

    file_paths = []
    for i in range(3):  # Let's create 3 small files for testing
        file_path = Path(_dir_path, f"test_file_{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"This is file {i}")
        file_paths.append(file_path)

    size_after = await efs_manager.get_project_node_data_size(
        project_id=_project_id, node_id=_node_id
    )
    assert size_after > size_before

    # Now we will check removal of write permissions
    for file_path in file_paths:
        assert_permissions(
            file_path,
            expected_readable=True,
            expected_writable=True,
            expected_executable=False,
        )

    await efs_manager.remove_project_node_data_write_permissions(
        project_id=_project_id, node_id=_node_id
    )

    for file_path in file_paths:
        assert_permissions(
            file_path,
            expected_readable=True,
            expected_writable=False,
            expected_executable=False,
        )
