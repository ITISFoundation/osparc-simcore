# pylint: disable=W0621
# pylint: disable=W0613
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, NamedTuple

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
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from settings_library.rabbit import RabbitSettings
from simcore_service_storage.api.rpc._async_jobs import AsyncJobNameData
from simcore_service_storage.api.rpc._data_export import AccessRightError
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


class UserWithFile(NamedTuple):
    user: UserID
    file: Path


@pytest.mark.parametrize(
    "project_params,_type",
    [
        (
            ProjectWithFilesParams(
                num_nodes=1,
                allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
                workspace_files_count=10,
            ),
            "file",
        ),
        (
            ProjectWithFilesParams(
                num_nodes=1,
                allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
                workspace_files_count=10,
            ),
            "folder",
        ),
    ],
    ids=str,
)
async def test_start_data_export_success(
    rpc_client: RabbitMQRPCClient,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    user_id: UserID,
    _type: Literal["file", "folder"],
):

    _, list_of_files = with_random_project_with_files
    workspace_files = [
        p for p in list(list_of_files.values())[0].keys() if "/workspace/" in p
    ]
    assert len(workspace_files) > 0
    file_or_folder_id: SimcoreS3FileID
    if _type == "file":
        file_or_folder_id = workspace_files[0]
    elif _type == "folder":
        parts = Path(workspace_files[0]).parts
        parts = parts[0 : parts.index("workspace") + 1]
        assert len(parts) > 0
        folder = Path(*parts)
        assert folder.name == "workspace"
        file_or_folder_id = f"{folder}"
    else:
        pytest.fail("invalid parameter: to_check")

    result = await async_jobs.submit_job(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name="start_data_export",
        job_id_data=AsyncJobNameData(user_id=user_id, product_name="osparc"),
        data_export_start=DataExportTaskStartInput(
            location_id=0,
            file_and_folder_ids=[file_or_folder_id],
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
            method_name="start_data_export",
            job_id_data=AsyncJobNameData(user_id=user_id, product_name="osparc"),
            data_export_start=DataExportTaskStartInput(
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
        job_id_data=AsyncJobNameData(
            user_id=faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
        job_id=_job_id,
    )
    assert isinstance(result, AsyncJobAbort)
    assert result.job_id == _job_id


async def test_get_data_export_status(rpc_client: RabbitMQRPCClient, faker: Faker):
    _job_id = AsyncJobId(faker.uuid4())
    result = await async_jobs.get_status(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        job_id_data=AsyncJobNameData(
            user_id=faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
    )
    assert isinstance(result, AsyncJobStatus)
    assert result.job_id == _job_id


async def test_get_data_export_result(rpc_client: RabbitMQRPCClient, faker: Faker):
    _job_id = AsyncJobId(faker.uuid4())
    result = await async_jobs.get_result(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        job_id_data=AsyncJobNameData(
            user_id=faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
    )
    assert isinstance(result, AsyncJobResult)


async def test_list_jobs(rpc_client: RabbitMQRPCClient, faker: Faker):
    result = await async_jobs.list_jobs(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=AsyncJobNameData(
            user_id=faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
        filter_="",
    )
    assert isinstance(result, list)
    assert all(isinstance(elm, AsyncJobGet) for elm in result)
