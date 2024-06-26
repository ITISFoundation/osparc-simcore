# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
from faker import Faker
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.efs_guardian import efs_manager
from simcore_service_efs_guardian.core.settings import AwsEfsSettings

pytest_simcore_core_services_selection = ["rabbit"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


async def test_rpc_create_project_specific_data_dir(
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
    app: FastAPI,
):
    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS

    _project_id = faker.uuid4()
    _node_id = faker.uuid4()
    _storage_directory_name = faker.name()

    result = await efs_manager.create_project_specific_data_dir(
        rpc_client,
        project_id=_project_id,
        node_id=_node_id,
        storage_directory_name=_storage_directory_name,
    )
    assert isinstance(result, Path)
    _expected_path = (
        aws_efs_settings.EFS_MOUNTED_PATH
        / aws_efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY
        / _project_id
        / _node_id
        / _storage_directory_name
    )
    assert _expected_path == result
    assert _expected_path.exists
