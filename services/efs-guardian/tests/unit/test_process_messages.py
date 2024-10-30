# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_efs_guardian.services.efs_manager import NodeID, ProjectID
from simcore_service_efs_guardian.services.process_messages import (
    process_dynamic_service_running_message,
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
            "EFS_DEFAULT_USER_SERVICE_SIZE_BYTES": "10000",
        },
    )


@patch("simcore_service_efs_guardian.services.process_messages.update_disk_usage")
async def test_process_msg(
    mock_update_disk_usage,
    faker: Faker,
    app: FastAPI,
    efs_cleanup: None,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    product_name: ProductName,
):
    # Create mock data for the message
    model_instance = DynamicServiceRunningMessage(
        project_id=project_id,
        node_id=node_id,
        user_id=user_id,
        product_name=product_name,
    )
    json_str = model_instance.json()
    model_bytes = json_str.encode("utf-8")

    _expected_project_node_states = [".data_assets", "home_user_workspace"]
    # Mock efs_manager and its methods
    mock_efs_manager = AsyncMock()
    app.state.efs_manager = mock_efs_manager
    mock_efs_manager.check_project_node_data_directory_exits.return_value = True
    mock_efs_manager.get_project_node_data_size.return_value = 4000
    mock_efs_manager.list_project_node_state_names.return_value = (
        _expected_project_node_states
    )

    result = await process_dynamic_service_running_message(app, data=model_bytes)

    # Check the actual arguments passed to notify_service_efs_disk_usage
    _, kwargs = mock_update_disk_usage.call_args
    assert kwargs["usage"]
    assert len(kwargs["usage"]) == 2
    for key, value in kwargs["usage"].items():
        assert key in _expected_project_node_states
        assert value.used == 4000
        assert value.free == 6000
        assert value.total == 10000
        assert value.used_percent == 40.0

    assert result is True


async def test_process_msg__dir_not_exists(
    app: FastAPI,
    efs_cleanup: None,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    product_name: ProductName,
):
    # Create mock data for the message
    model_instance = DynamicServiceRunningMessage(
        project_id=project_id,
        node_id=node_id,
        user_id=user_id,
        product_name=product_name,
    )
    json_str = model_instance.json()
    model_bytes = json_str.encode("utf-8")

    result = await process_dynamic_service_running_message(app, data=model_bytes)
    assert result is True
