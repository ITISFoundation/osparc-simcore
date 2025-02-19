# pylint: disable=W0621
# pylint: disable=W0613
from pathlib import Path
from typing import Awaitable, Callable

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.data_export_async_jobs import (
    DataExportTaskStartInput,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from servicelib.rabbitmq.rpc_interfaces.storage import data_export
from settings_library.rabbit import RabbitSettings
from simcore_service_storage.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.rabbit_service",
]


pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]


@pytest.fixture
async def mock_rabbit_setup(mocker: MockerFixture):
    # fixture to avoid mocking the rabbit
    pass


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


async def test_start_data_export(rpc_client: RabbitMQRPCClient, faker: Faker):
    result = await data_export.start_data_export(
        rpc_client,
        paths=DataExportTaskStartInput(
            user_id=1, location_id=0, paths=[Path(faker.file_path())]
        ),
    )
    assert isinstance(result, AsyncJobGet)


async def test_abort_data_export(rpc_client: RabbitMQRPCClient, faker: Faker):
    _job_id = AsyncJobId(faker.uuid4())
    result = await async_jobs.abort(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        access_data=None,
    )
    assert isinstance(result, AsyncJobAbort)
    assert result.job_id == _job_id


async def test_get_data_export_status(rpc_client: RabbitMQRPCClient, faker: Faker):
    _job_id = AsyncJobId(faker.uuid4())
    result = await async_jobs.get_status(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        access_data=None,
    )
    assert isinstance(result, AsyncJobStatus)
    assert result.job_id == _job_id


async def test_get_data_export_result(rpc_client: RabbitMQRPCClient, faker: Faker):
    _job_id = AsyncJobId(faker.uuid4())
    result = await async_jobs.get_result(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        access_data=None,
    )
    assert isinstance(result, AsyncJobResult)


async def test_list_jobs(rpc_client: RabbitMQRPCClient, faker: Faker):
    result = await async_jobs.list_jobs(
        rpc_client, rpc_namespace=STORAGE_RPC_NAMESPACE, filter=""
    )
    assert isinstance(result, list)
    assert all(isinstance(elm, AsyncJobGet) for elm in result)
