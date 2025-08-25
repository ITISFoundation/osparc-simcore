# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import json

import pytest
from async_asgi_testclient import TestClient
from common_library.serialization import model_dump_with_secrets
from fastapi import FastAPI, status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.long_running_tasks._manager import FastAPILongRunningManager
from servicelib.fastapi.long_running_tasks.server import (
    get_long_running_manager_from_app,
)
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.task import TaskRegistry
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar._meta import API_VTAG

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def sleeping_very_long(progress: TaskProgress) -> None:
    _ = progress
    await asyncio.sleep(10_000)


TaskRegistry.register(sleeping_very_long)


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
    mock_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
            "RABBIT_SETTINGS": json.dumps(
                model_dump_with_secrets(rabbit_service, show_secrets=True)
            ),
        },
    )


def _assert_long_running_tasks_count(
    long_running_manager: FastAPILongRunningManager, *, count: int
) -> None:
    assert (
        len(long_running_manager.tasks_manager._created_tasks) == count  # noqa: SLF001
    )


async def test_cleanup_long_running_tasks(test_client: TestClient) -> None:
    app: FastAPI = test_client.application
    long_running_manager = get_long_running_manager_from_app(app)

    _assert_long_running_tasks_count(long_running_manager, count=0)

    await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        sleeping_very_long.__name__,
    )

    _assert_long_running_tasks_count(long_running_manager, count=1)

    response = await test_client.delete(f"/{API_VTAG}/long-running-tasks")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response

    _assert_long_running_tasks_count(long_running_manager, count=0)
