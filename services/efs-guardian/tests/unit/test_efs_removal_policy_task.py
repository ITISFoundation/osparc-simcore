# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_efs_guardian.core.settings import (
    ApplicationSettings,
    AwsEfsSettings,
)
from simcore_service_efs_guardian.services.background_tasks import removal_policy_task
from simcore_service_efs_guardian.services.efs_manager import (
    EfsManager,
    NodeID,
    ProjectID,
)

pytest_simcore_core_services_selection = ["postgres", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    wait_for_postgres_ready_and_db_migrated: None,
    with_disabled_redis_and_background_tasks: None,
):
    # set environs
    monkeypatch.delenv("EFS_GUARDIAN_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "efs-guardian-service-pg-client",
            "EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA": "01:00:00",
        },
    )


@pytest.fixture
async def user_in_db(
    app: FastAPI,
    user: dict[str, Any],
    user_id: UserID,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects a user in db
    """
    assert user_id == user["id"]
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        app.state.engine,
        table=users,
        values=user,
        pk_col=users.c.id,
        pk_value=user["id"],
    ) as row:
        yield row


@pytest.fixture
async def project_in_db(
    app: FastAPI,
    user_in_db: dict,
    project_data: dict[str, Any],
    project_id: ProjectID,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects a project in db
    """
    assert f"{project_id}" == project_data["uuid"]
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        app.state.engine,
        table=projects,
        values=project_data,
        pk_col=projects.c.uuid,
        pk_value=project_data["uuid"],
    ) as row:
        yield row


@patch("simcore_service_efs_guardian.services.background_tasks.get_redis_lock_client")
@patch("simcore_service_efs_guardian.services.background_tasks.lock_project")
async def test_efs_removal_policy_task(
    mock_lock_project: MagicMock,
    mock_get_redis_lock_client: MagicMock,
    faker: Faker,
    app: FastAPI,
    efs_cleanup: None,
    project_id: ProjectID,
    node_id: NodeID,
    project_in_db: dict,
):
    # 1. Nothing should happen
    await removal_policy_task(app)
    assert not mock_lock_project.called

    # 2. Lets create some project with data
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

    with patch(
        "simcore_service_efs_guardian.services.efs_manager.os.chown"
    ) as mocked_chown:
        await efs_manager.create_project_specific_data_dir(
            project_id=project_id,
            node_id=node_id,
            storage_directory_name=_storage_directory_name,
        )
        assert mocked_chown.called

    file_paths = []
    for i in range(3):  # Let's create 3 small files for testing
        file_path = Path(_dir_path, f"test_file_{i}.txt")
        file_path.write_text(f"This is file {i}")
        file_paths.append(file_path)

    # 3. Nothing should happen
    await removal_policy_task(app)
    assert not mock_lock_project.called

    # 4. We will artifically change the project last change date
    app_settings: ApplicationSettings = app.state.settings
    _current_timestamp = datetime.now()
    _old_timestamp = (
        _current_timestamp
        - app_settings.EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA
        - timedelta(days=1)
    )
    async with transaction_context(app.state.engine) as conn:
        result = await conn.execute(
            projects.update()
            .values(last_change_date=_old_timestamp)
            .where(projects.c.uuid == f"{project_id}")
        )
        result_row_count: int = result.rowcount
        assert result_row_count == 1  # nosec

    # 5. Now removal policy should remove those data
    await removal_policy_task(app)
    assert mock_lock_project.assert_called_once
    assert mock_get_redis_lock_client.assert_called_once
    projects_list = await efs_manager.list_projects_across_whole_efs()
    assert projects_list == []
