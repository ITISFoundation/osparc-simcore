from collections.abc import Callable
from typing import Any, Final

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
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
from models_library.generics import Envelope
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from servicelib.aiohttp import status
from simcore_service_webserver.tasks import _tasks_service
from simcore_service_webserver.tasks._controller import _rest

API_VERSION = "v0"


PREFIX = "/" + API_VERSION + "/tasks"
_faker = Faker()
_user_roles: Final[list[UserRole]] = [
    UserRole.GUEST,
    UserRole.USER,
    UserRole.TESTER,
    UserRole.PRODUCT_OWNER,
    UserRole.ADMIN,
]


@pytest.fixture(name="create_consume_events_mock")
def create_consume_events_mock_fixture(
    mocker: MockerFixture,
) -> Callable[[Any], None]:
    def _(result_or_exception: Any):
        async def mock_consume_events(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception
            # Yield the mock events
            for event_id, event_data in result_or_exception:
                yield event_id, event_data

        mock_task_manager = mocker.MagicMock()
        mock_task_manager.consume_task_events = mock_consume_events
        mocker.patch.object(
            _rest,
            "get_task_manager",
            return_value=mock_task_manager,
        )

    return _


class MockEvent:
    def __init__(self, event_type: str, event_data: dict[str, Any]):
        self.type = event_type
        self.data = event_data


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            [
                AsyncJobGet(
                    job_id=AsyncJobId(_faker.uuid4()),
                    job_name="task_name",
                )
            ],
            status.HTTP_200_OK,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda x: type(x).__name__,
)
@pytest.mark.usefixtures("user_role", "logged_user")
async def test_get_user_async_jobs(
    client: TestClient,
    create_backend_mock: Callable[[str, str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_backend_mock(
        _rest.__name__,
        f"_tasks_service.{_tasks_service.list_tasks.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        Envelope[list[TaskGet]].model_validate(await response.json())


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            AsyncJobStatus(
                job_id=AsyncJobId(f"{_faker.uuid4()}"),
                progress=ProgressReport(actual_value=0.5, total=1.0),
                done=False,
            ),
            status.HTTP_200_OK,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobMissingError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
    ],
    ids=lambda x: type(x).__name__,
)
@pytest.mark.usefixtures("user_role", "logged_user")
async def test_get_async_jobs_status(
    client: TestClient,
    create_backend_mock: Callable[[str, str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(_faker.uuid4())
    create_backend_mock(
        _rest.__name__,
        f"_tasks_service.{_tasks_service.get_task_status.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{_job_id}")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        response_body_data = (
            Envelope[TaskStatus].model_validate(await response.json()).data
        )
        assert response_body_data is not None


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (JobNotDoneError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
        (AsyncJobResult(result=None), status.HTTP_200_OK),
        (JobError(job_id=_faker.uuid4()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobAbortedError(job_id=_faker.uuid4()), status.HTTP_410_GONE),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobMissingError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
    ],
    ids=lambda x: type(x).__name__,
)
@pytest.mark.usefixtures("user_role", "logged_user")
async def test_get_async_job_result(
    client: TestClient,
    create_backend_mock: Callable[[str, str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_backend_mock(
        _rest.__name__,
        f"_tasks_service.{_tasks_service.get_task_result.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{_job_id}/result")
    assert response.status == expected_status


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            [
                ("event-1", MockEvent("status", {"status": "running"})),
                ("event-2", MockEvent("progress", {"percent": 50})),
                ("event-3", MockEvent("status", {"status": "completed"})),
            ],
            status.HTTP_200_OK,
        ),
        ([], status.HTTP_200_OK),  # No events
    ],
    ids=lambda x: (
        "with_events" if x and isinstance(x, list) and len(x) > 0 else "no_events"
    ),
)
@pytest.mark.usefixtures("user_role", "logged_user")
async def test_get_async_job_stream(
    client: TestClient,
    create_consume_events_mock: Callable[[Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_consume_events_mock(backend_result_or_exception)

    _task_id = AsyncJobId(faker.uuid4())

    response = await client.get(
        f"/{API_VERSION}/tasks/{_task_id}/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert response.status == expected_status

    if response.status == status.HTTP_200_OK:
        assert response.headers.get("Content-Type") == "text/event-stream"

        content = await response.text()
        if backend_result_or_exception:
            assert "data:" in content or len(backend_result_or_exception) == 0
        else:
            assert content == ""
