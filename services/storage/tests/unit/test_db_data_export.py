# pylint: disable=W0621
# pylint: disable=W0613
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Awaitable, Callable, NamedTuple

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
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_service_storage.api.rpc._data_export import AccessRightError
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.models import FileMetaData
from sqlalchemy.ext.asyncio import AsyncEngine

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


class UserWithFile(NamedTuple):
    user: UserID
    file: Path


@pytest.fixture
async def user_owner_file(
    user_id: UserID, project_id: ProjectID, sqlalchemy_async_engine: AsyncEngine
):
    async with sqlalchemy_async_engine.connect() as conn:
        file_meta_data.insert()


async def test_start_data_export_success(
    rpc_client: RabbitMQRPCClient, output_file: FileMetaData, user_id: UserID
):

    result = await async_jobs.submit_job(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_name="start_data_export",
        data_export_start=DataExportTaskStartInput(
            user_id=user_id,
            product_name="osparc",
            location_id=output_file.location_id,
            file_and_folder_ids=[output_file.file_id],
        ),
    )
    assert isinstance(result, AsyncJobGet)


async def test_start_data_export_fail(
    rpc_client: RabbitMQRPCClient, user_id: UserID, faker: Faker
):

    with pytest.raises(AccessRightError):
        _ = await async_jobs.submit_job(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_name="start_data_export",
            data_export_start=DataExportTaskStartInput(
                user_id=user_id,
                product_name="osparc",
                location_id=0,
                file_and_folder_ids=[
                    f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"
                ],
            ),
        )


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
        rpc_client, rpc_namespace=STORAGE_RPC_NAMESPACE, filter_=""
    )
    assert isinstance(result, list)
    assert all(isinstance(elm, AsyncJobGet) for elm in result)
