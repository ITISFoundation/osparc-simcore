# pylint: disable=W0621
# pylint: disable=W0613
# pylint: disable=R6301
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NamedTuple
from uuid import UUID

import pytest
from celery.exceptions import CeleryError
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.tasks import TaskResult
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.data_export_async_jobs import (
    DataExportTaskStartInput,
)
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from servicelib.rabbitmq.rpc_interfaces.storage.data_export import start_data_export
from settings_library.rabbit import RabbitSettings
from simcore_service_storage.api.rpc._data_export import AccessRightError
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.modules.celery.client import TaskUUID
from simcore_service_storage.modules.celery.models import TaskState, TaskStatus
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_plugins = [
    "pytest_simcore.rabbit_service",
]


pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]

_faker = Faker()


@dataclass
class _MockCeleryClient:
    send_task_object: UUID | Exception | None = None
    get_task_status_object: TaskStatus | Exception | None = None
    get_task_result_object: TaskResult | Exception | None = None
    get_task_uuids_object: set[UUID] | Exception | None = None
    abort_task_object: Exception | None = None

    async def send_task(self, *args, **kwargs) -> TaskUUID:
        assert self.send_task_object is not None
        if isinstance(self.send_task_object, Exception):
            raise self.send_task_object
        return self.send_task_object

    async def get_task_status(self, *args, **kwargs) -> TaskStatus:
        assert self.get_task_status_object is not None
        if isinstance(self.get_task_status_object, Exception):
            raise self.get_task_status_object
        return self.get_task_status_object

    async def get_task_result(self, *args, **kwargs) -> Any:
        assert self.get_task_result_object is not None
        if isinstance(self.get_task_result_object, Exception):
            raise self.get_task_result_object
        return self.get_task_result_object

    async def get_task_uuids(self, *args, **kwargs) -> set[TaskUUID]:
        assert self.get_task_uuids_object is not None
        if isinstance(self.get_task_uuids_object, Exception):
            raise self.get_task_uuids_object
        return self.get_task_uuids_object

    async def abort_task(self, *args, **kwargs) -> None:
        if isinstance(self.abort_task_object, Exception):
            raise self.abort_task_object
        return self.abort_task_object


@pytest.fixture
async def mock_celery_client(
    mocker: MockerFixture,
    request: pytest.FixtureRequest,
) -> _MockCeleryClient:
    params = request.param if hasattr(request, "param") else {}
    _celery_client = _MockCeleryClient(
        send_task_object=params.get("send_task_object", None),
        get_task_status_object=params.get("get_task_status_object", None),
        get_task_result_object=params.get("get_task_result_object", None),
        get_task_uuids_object=params.get("get_task_uuids_object", None),
        abort_task_object=params.get("abort_task_object", None),
    )
    mocker.patch(
        "simcore_service_storage.api.rpc._async_jobs.get_celery_client",
        return_value=_celery_client,
    )
    mocker.patch(
        "simcore_service_storage.api.rpc._data_export.get_celery_client",
        return_value=_celery_client,
    )
    return _celery_client


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
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "project_params,selection_type",
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
@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {"send_task_object": TaskUUID(_faker.uuid4())},
    ],
    indirect=True,
)
async def test_start_data_export_success(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    user_id: UserID,
    selection_type: Literal["file", "folder"],
):
    _, list_of_files = with_random_project_with_files
    workspace_files = [
        p for p in next(iter(list_of_files.values())) if "/workspace/" in p
    ]
    assert len(workspace_files) > 0
    file_or_folder_id: SimcoreS3FileID
    if selection_type == "file":
        file_or_folder_id = workspace_files[0]
    elif selection_type == "folder":
        parts = Path(workspace_files[0]).parts
        parts = parts[0 : parts.index("workspace") + 1]
        assert len(parts) > 0
        folder = Path(*parts)
        assert folder.name == "workspace"
        file_or_folder_id = f"{folder}"
    else:
        pytest.fail("invalid parameter: to_check")

    result = await start_data_export(
        rpc_client,
        job_id_data=AsyncJobNameData(user_id=user_id, product_name="osparc"),
        data_export_start=DataExportTaskStartInput(
            location_id=0,
            file_and_folder_ids=[file_or_folder_id],
        ),
    )
    assert isinstance(result, AsyncJobGet)


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=1,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
            workspace_files_count=10,
        ),
    ],
    ids=str,
)
@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {"send_task_object": CeleryError("error")},
    ],
    indirect=True,
)
async def test_start_data_export_scheduler_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    user_id: UserID,
):

    _, list_of_files = with_random_project_with_files
    workspace_files = [
        p for p in list(list_of_files.values())[0].keys() if "/workspace/" in p
    ]
    assert len(workspace_files) > 0
    file_or_folder_id = workspace_files[0]

    with pytest.raises(JobSchedulerError):
        _ = await start_data_export(
            rpc_client,
            job_id_data=AsyncJobNameData(user_id=user_id, product_name="osparc"),
            data_export_start=DataExportTaskStartInput(
                location_id=0,
                file_and_folder_ids=[file_or_folder_id],
            ),
        )


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {"send_task_object": TaskUUID(_faker.uuid4())},
    ],
    indirect=True,
)
async def test_start_data_export_access_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    user_id: UserID,
    faker: Faker,
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


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {
            "abort_task_object": None,
            "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
        },
    ],
    indirect=True,
)
async def test_abort_data_export_success(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    assert mock_celery_client.get_task_uuids_object is not None
    assert not isinstance(mock_celery_client.get_task_uuids_object, Exception)
    await async_jobs.abort(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=AsyncJobNameData(
            user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
        job_id=next(iter(mock_celery_client.get_task_uuids_object)),
    )


@pytest.mark.parametrize(
    "mock_celery_client, expected_exception_type",
    [
        ({"abort_task_object": None, "get_task_uuids_object": []}, JobMissingError),
        (
            {
                "abort_task_object": CeleryError("error"),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobSchedulerError,
        ),
    ],
    indirect=["mock_celery_client"],
)
async def test_abort_data_export_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception_type: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    with pytest.raises(expected_exception_type):
        await async_jobs.abort(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id_data=AsyncJobNameData(
                user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
            ),
            job_id=_job_id,
        )


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {
            "get_task_status_object": TaskStatus(
                task_uuid=TaskUUID(_faker.uuid4()),
                task_state=TaskState.RUNNING,
                progress_report=ProgressReport(actual_value=0),
            ),
            "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
        },
    ],
    indirect=True,
)
async def test_get_data_export_status(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    result = await async_jobs.get_status(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        job_id_data=AsyncJobNameData(
            user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
    )
    assert isinstance(result, AsyncJobStatus)
    assert result.job_id == _job_id


@pytest.mark.parametrize(
    "mock_celery_client, expected_exception_type",
    [
        (
            {"get_task_status_object": None, "get_task_uuids_object": []},
            JobMissingError,
        ),
        (
            {
                "get_task_status_object": CeleryError("error"),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobSchedulerError,
        ),
    ],
    indirect=["mock_celery_client"],
)
async def test_get_data_export_status_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception_type: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    with pytest.raises(expected_exception_type):
        _ = await async_jobs.get_status(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=_job_id,
            job_id_data=AsyncJobNameData(
                user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
            ),
        )


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {
            "get_task_status_object": TaskStatus(
                task_uuid=TaskUUID(_faker.uuid4()),
                task_state=TaskState.SUCCESS,
                progress_report=ProgressReport(actual_value=100),
            ),
            "get_task_result_object": "result",
            "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
        },
    ],
    indirect=True,
)
async def test_get_data_export_result_success(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    result = await async_jobs.get_result(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=_job_id,
        job_id_data=AsyncJobNameData(
            user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
    )
    assert isinstance(result, AsyncJobResult)


@pytest.mark.parametrize(
    "mock_celery_client, expected_exception",
    [
        (
            {
                "get_task_status_object": TaskStatus(
                    task_uuid=TaskUUID(_faker.uuid4()),
                    task_state=TaskState.RUNNING,
                    progress_report=ProgressReport(actual_value=50),
                ),
                "get_task_result_object": _faker.text(),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobNotDoneError,
        ),
        (
            {
                "get_task_status_object": TaskStatus(
                    task_uuid=TaskUUID(_faker.uuid4()),
                    task_state=TaskState.ABORTED,
                    progress_report=ProgressReport(actual_value=100),
                ),
                "get_task_result_object": _faker.text(),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobAbortedError,
        ),
        (
            {
                "get_task_status_object": TaskStatus(
                    task_uuid=TaskUUID(_faker.uuid4()),
                    task_state=TaskState.ERROR,
                    progress_report=ProgressReport(actual_value=100),
                ),
                "get_task_result_object": _faker.text(),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobError,
        ),
        (
            {
                "get_task_status_object": CeleryError("error"),
                "get_task_result_object": _faker.text(),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobSchedulerError,
        ),
        (
            {
                "get_task_uuids_object": [],
            },
            JobMissingError,
        ),
    ],
    indirect=["mock_celery_client"],
)
async def test_get_data_export_result_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())

    with pytest.raises(expected_exception):
        _ = await async_jobs.get_result(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=_job_id,
            job_id_data=AsyncJobNameData(
                user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
            ),
        )


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {"get_task_uuids_object": [_faker.uuid4() for _ in range(_faker.pyint(1, 10))]},
    ],
    indirect=True,
)
async def test_list_jobs_success(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: MockerFixture,
):
    result = await async_jobs.list_jobs(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=AsyncJobNameData(
            user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
        filter_="",
    )
    assert isinstance(result, list)
    assert all(isinstance(elm, AsyncJobGet) for elm in result)


@pytest.mark.parametrize(
    "mock_celery_client",
    [
        {"get_task_uuids_object": CeleryError("error")},
    ],
    indirect=True,
)
async def test_list_jobs_error(
    rpc_client: RabbitMQRPCClient,
    mock_celery_client: MockerFixture,
):
    with pytest.raises(JobSchedulerError):
        _ = await async_jobs.list_jobs(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id_data=AsyncJobNameData(
                user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
            ),
            filter_="",
        )
