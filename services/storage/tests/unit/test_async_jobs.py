# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from dataclasses import dataclass
from typing import Any
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
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from simcore_service_storage.modules.celery._task import _wrap_exception
from simcore_service_storage.modules.celery.client import TaskUUID
from simcore_service_storage.modules.celery.models import TaskState, TaskStatus

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
        _ = args
        _ = kwargs
        assert self.send_task_object is not None
        if isinstance(self.send_task_object, Exception):
            raise self.send_task_object
        return self.send_task_object

    async def get_task_status(self, *args, **kwargs) -> TaskStatus:
        _ = args
        _ = kwargs
        assert self.get_task_status_object is not None
        if isinstance(self.get_task_status_object, Exception):
            raise self.get_task_status_object
        return self.get_task_status_object

    async def get_task_result(self, *args, **kwargs) -> Any:
        _ = args
        _ = kwargs
        assert self.get_task_result_object is not None
        if isinstance(self.get_task_result_object, Exception):
            return _wrap_exception(self.get_task_result_object)
        return self.get_task_result_object

    async def get_task_uuids(self, *args, **kwargs) -> set[TaskUUID]:
        _ = args
        _ = kwargs
        assert self.get_task_uuids_object is not None
        if isinstance(self.get_task_uuids_object, Exception):
            raise self.get_task_uuids_object
        return self.get_task_uuids_object

    async def abort_task(self, *args, **kwargs) -> None:
        _ = args
        _ = kwargs
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
        "simcore_service_storage.api.rpc._simcore_s3.get_celery_client",
        return_value=_celery_client,
    )
    return _celery_client


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
async def test_async_jobs_abort(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    assert mock_celery_client.get_task_uuids_object is not None
    assert not isinstance(mock_celery_client.get_task_uuids_object, Exception)
    await async_jobs.cancel(
        storage_rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=AsyncJobNameData(
            user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
        ),
        job_id=next(iter(mock_celery_client.get_task_uuids_object)),
    )


@pytest.mark.parametrize(
    "mock_celery_client, expected_exception_type",
    [
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
async def test_async_jobs_cancel(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception_type: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    with pytest.raises(expected_exception_type):
        await async_jobs.cancel(
            storage_rabbitmq_rpc_client,
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
                task_state=TaskState.PENDING,
                progress_report=ProgressReport(actual_value=0),
            ),
            "get_task_uuids_object": [],
        },
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
async def test_async_jobs_status(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    result = await async_jobs.status(
        storage_rabbitmq_rpc_client,
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
            {
                "get_task_status_object": CeleryError("error"),
                "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
            },
            JobSchedulerError,
        ),
    ],
    indirect=["mock_celery_client"],
)
async def test_async_jobs_status_error(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception_type: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    with pytest.raises(expected_exception_type):
        await async_jobs.status(
            storage_rabbitmq_rpc_client,
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
                progress_report=ProgressReport(actual_value=1, total=1),
            ),
            "get_task_result_object": "result",
            "get_task_uuids_object": [AsyncJobId(_faker.uuid4())],
        },
    ],
    indirect=True,
)
async def test_async_jobs_result_success(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())
    result = await async_jobs.result(
        storage_rabbitmq_rpc_client,
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
                    progress_report=ProgressReport(actual_value=0.5, total=1.0),
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
                    progress_report=ProgressReport(actual_value=1.0, total=1.0),
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
                    progress_report=ProgressReport(actual_value=1.0, total=1.0),
                ),
                "get_task_result_object": Exception("generic exception"),
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
                "get_task_status_object": TaskStatus(
                    task_uuid=TaskUUID(_faker.uuid4()),
                    task_state=TaskState.PENDING,
                    progress_report=ProgressReport(actual_value=0.0),
                ),
                "get_task_uuids_object": [],
            },
            JobNotDoneError,
        ),
    ],
    indirect=["mock_celery_client"],
)
async def test_async_jobs_result_error(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: _MockCeleryClient,
    expected_exception: type[Exception],
):
    job_ids = mock_celery_client.get_task_uuids_object
    assert job_ids is not None
    assert not isinstance(job_ids, Exception)
    _job_id = next(iter(job_ids)) if len(job_ids) > 0 else AsyncJobId(_faker.uuid4())

    with pytest.raises(expected_exception):
        await async_jobs.result(
            storage_rabbitmq_rpc_client,
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
async def test_async_jobs_list_jobs(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: MockerFixture,
):
    result = await async_jobs.list_jobs(
        storage_rabbitmq_rpc_client,
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
async def test_async_jobs_list_jobs_error(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    mock_celery_client: MockerFixture,
):
    with pytest.raises(JobSchedulerError):
        await async_jobs.list_jobs(
            storage_rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id_data=AsyncJobNameData(
                user_id=_faker.pyint(min_value=1, max_value=100), product_name="osparc"
            ),
            filter_="",
        )
