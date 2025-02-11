from pathlib import Path
from typing import Awaitable, Callable

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskStatus
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.storage import zipping
from settings_library.rabbit import RabbitSettings
from simcore_service_storage.api.rabbitmq_rpc._zipping import TaskId
from simcore_service_storage.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.rabbit_service",
]


pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]


@pytest.fixture
async def app_environment(
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    monkeypatch: pytest.MonkeyPatch,
):
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
        },
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.STORAGE_RABBITMQ

    return new_envs


@pytest.fixture
async def rpc_client(
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_start_zipping(rpc_client: RabbitMQRPCClient, faker: Faker):
    result = await zipping.start_zipping(
        rpc_client, paths=ZipTaskStartInput(paths=[Path(faker.file_path())])
    )
    assert isinstance(result, TaskGet)


async def test_abort_zipping(rpc_client: RabbitMQRPCClient, faker: Faker):
    _task_id = TaskId(f"{faker.uuid4()}")
    result = await zipping.abort_zipping(rpc_client, task_id=_task_id)
    assert isinstance(result, ZipTaskAbortOutput)
    assert result.task_id == _task_id


async def test_get_zipping_status(rpc_client: RabbitMQRPCClient, faker: Faker):
    _task_id = TaskId(f"{faker.uuid4()}")
    result = await zipping.get_zipping_status(rpc_client, task_id=_task_id)
    assert isinstance(result, TaskStatus)
    assert result.task_progress.task_id == _task_id
