# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

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
    with_disabled_redis_and_background_tasks: None,
    with_disabled_postgres: None,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


def assert_permissions(
    file_path: Path,
    expected_readable: bool,
    expected_writable: bool,
    expected_executable: bool,
):
    file_stat = Path.stat(file_path)
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
    app: FastAPI,
    efs_cleanup: None,
    project_id: ProjectID,
    node_id: NodeID,
):
    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS

    _storage_directory_name = faker.word()
    _dir_path = (
        aws_efs_settings.EFS_MOUNTED_PATH
        / aws_efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY
        / f"{project_id}"
        / f"{node_id}"
        / f"{_storage_directory_name}"
    )

    efs_manager: EfsManager = app.state.efs_manager

    assert (
        await efs_manager.check_project_node_data_directory_exits(
            project_id=project_id, node_id=node_id
        )
        is False
    )

    with pytest.raises(FileNotFoundError):
        await efs_manager.list_project_node_state_names(
            project_id=project_id, node_id=node_id
        )

    with patch(
        "simcore_service_efs_guardian.services.efs_manager.os.chown"
    ) as mocked_chown:
        await efs_manager.create_project_specific_data_dir(
            project_id=project_id,
            node_id=node_id,
            storage_directory_name=_storage_directory_name,
        )
        assert mocked_chown.called

    assert (
        await efs_manager.check_project_node_data_directory_exits(
            project_id=project_id, node_id=node_id
        )
        is True
    )

    project_node_state_names = await efs_manager.list_project_node_state_names(
        project_id=project_id, node_id=node_id
    )
    assert project_node_state_names == [_storage_directory_name]

    size_before = await efs_manager.get_project_node_data_size(
        project_id=project_id, node_id=node_id
    )

    file_paths = []
    for i in range(3):  # Let's create 3 small files for testing
        file_path = Path(_dir_path, f"test_file_{i}.txt")
        file_path.write_text(f"This is file {i}")
        file_paths.append(file_path)

    size_after = await efs_manager.get_project_node_data_size(
        project_id=project_id, node_id=node_id
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
        project_id=project_id, node_id=node_id
    )

    for file_path in file_paths:
        assert_permissions(
            file_path,
            expected_readable=True,
            expected_writable=False,
            expected_executable=False,
        )
