# pylint: disable=redefined-outer-name

import datetime
import json
from collections.abc import Callable
from uuid import uuid4

import pytest
from celery_library.errors import TaskOrGroupNotFoundError
from faker import Faker
from models_library.api_schemas_webserver.functions import (
    FunctionClass,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.celery import TaskState, TaskStatus, TaskUUID
from models_library.functions import RegisteredFunction, RegisteredFunctionJob
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server._service_function_jobs import FunctionJobService
from simcore_service_api_server._service_function_jobs_task_client import (
    FunctionJobTaskClientService,
    _celery_task_status,
)
from simcore_service_api_server._service_functions import FunctionService
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.api.dependencies.authentication import Identity
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.schemas.functions import FunctionJobCreationTaskStatus
from simcore_service_api_server.services_http.webserver import AuthSession
from simcore_service_api_server.services_rpc.storage import StorageService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient
from sqlalchemy.ext.asyncio import AsyncEngine

_faker = Faker()


@pytest.fixture
async def create_mock_task_manager(
    mocker: MockerFixture,
) -> Callable[[TaskStatus | Exception], MockType]:
    def _(status_or_exception: TaskStatus | Exception) -> MockType:
        mock_task_manager = mocker.Mock(spec=TaskManager)
        if isinstance(status_or_exception, Exception):

            async def _raise(*args, **kwargs):
                raise status_or_exception

            mock_task_manager.get_status.side_effect = _raise
        else:
            mock_task_manager.get_status.return_value = status_or_exception
        return mock_task_manager

    return _


@pytest.mark.parametrize(
    "status_or_exception",
    [
        TaskStatus(
            task_uuid=TypeAdapter(TaskUUID).validate_python(_faker.uuid4()),
            task_state=state,
            progress_report=ProgressReport(actual_value=3.14),
        )
        for state in list(TaskState)
    ]
    + [TaskOrGroupNotFoundError(task_uuid=_faker.uuid4(), owner_metadata=json.dumps({"owner": "test-owner"}))],
)
@pytest.mark.parametrize("job_creation_task_id", [_faker.uuid4(), None])
async def test_celery_status_conversion(
    status_or_exception: TaskStatus | Exception,
    job_creation_task_id: str | None,
    create_mock_task_manager: Callable[[TaskStatus | Exception], MockType],
    user_id: UserID,
    product_name: ProductName,
):
    mock_task_manager = create_mock_task_manager(status_or_exception)

    status = await _celery_task_status(
        job_creation_task_id=job_creation_task_id,
        task_manager=mock_task_manager,
        user_id=user_id,
        product_name=product_name,
    )

    if job_creation_task_id is None:
        assert status == FunctionJobCreationTaskStatus.NOT_YET_SCHEDULED
    elif isinstance(status_or_exception, TaskOrGroupNotFoundError):
        assert status == FunctionJobCreationTaskStatus.ERROR
    elif isinstance(status_or_exception, TaskStatus):
        assert status == FunctionJobCreationTaskStatus[status_or_exception.task_state.name]
    else:
        pytest.fail("Unexpected test input")


@pytest.fixture
def registered_project_function() -> RegisteredFunction:
    return RegisteredProjectFunction(
        title="test_function",
        function_class=FunctionClass.PROJECT,
        description="A test function",
        input_schema=JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        ),
        output_schema=JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ),
        default_inputs=None,
        project_id=uuid4(),
        uid=uuid4(),
        created_at=datetime.datetime.now(datetime.UTC),
        modified_at=datetime.datetime.now(datetime.UTC),
    )


@pytest.fixture
def cached_function_job(
    registered_project_function: RegisteredFunction,
) -> RegisteredFunctionJob:
    return RegisteredProjectFunctionJob(
        uid=uuid4(),
        function_uid=registered_project_function.uid,
        title="Cached job",
        description="A cached function job",
        inputs={"input1": 42},
        outputs={"output1": "result"},
        project_job_id=uuid4(),
        function_class=FunctionClass.PROJECT,
        job_creation_task_id=None,
        created_at=datetime.datetime.now(datetime.UTC),
    )


async def test_create_function_job_creation_tasks_all_cached(
    mocker: MockerFixture,
    user_id: UserID,
    product_name: ProductName,
    registered_project_function: RegisteredFunction,
    cached_function_job: RegisteredFunctionJob,
):
    mock_web_rpc = mocker.AsyncMock(spec=WbApiRpcClient)
    mock_web_rpc.find_cached_function_jobs.return_value = [
        cached_function_job,
    ]

    service = FunctionJobTaskClientService(
        user_id=user_id,
        product_name=product_name,
        _web_rpc_client=mock_web_rpc,
        _storage_client=mocker.AsyncMock(spec=StorageService),
        _job_service=mocker.AsyncMock(spec=JobService),
        _function_service=mocker.AsyncMock(spec=FunctionService),
        _function_job_service=mocker.AsyncMock(spec=FunctionJobService),
        _webserver_api=mocker.AsyncMock(spec=AuthSession),
        _celery_task_manager=mocker.Mock(spec=TaskManager),
        _async_pg_engine=mocker.MagicMock(spec=AsyncEngine),
    )

    identity = Identity(
        user_id=user_id,
        product_name=product_name,
        email="test@example.com",
    )

    result = await service.create_function_job_creation_tasks(
        function=registered_project_function,
        function_inputs=[{"input1": 42}],
        user_identity=identity,
        pricing_spec=None,
        job_links=mocker.MagicMock(spec=JobLinks),
    )

    assert len(result) == 1
    assert result[0] == cached_function_job
    mock_function_job_service = service._function_job_service  # noqa: SLF001
    mock_function_job_service.batch_pre_register_function_jobs.assert_not_called()
