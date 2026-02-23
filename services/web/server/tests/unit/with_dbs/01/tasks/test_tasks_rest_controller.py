# pylint: disable=unused-argument

from collections.abc import Callable
from typing import Any, Final

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskStatus,
)
from models_library.generics import Envelope
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_mock import HandlerMockFactory
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
    type: str
    data: dict[str, Any]


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            [
                AsyncJobGet(
                    job_id=_faker.uuid4(),
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
    mock_handler_in_task_service: HandlerMockFactory,
    backend_result_or_exception: Any,
    expected_status: int,
):
    mock_handler_in_task_service(
        _tasks_service.list_tasks.__name__,
        side_effect=backend_result_or_exception,
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
                job_id=_faker.uuid4(),
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
    mock_handler_in_task_service: HandlerMockFactory,
    backend_result_or_exception: Any,
    expected_status: int,
):
    mock_handler_in_task_service(
        _tasks_service.get_task_status.__name__,
        side_effect=backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{_faker.uuid4()}")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        response_body_data = Envelope[TaskStatus].model_validate(await response.json()).data
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
    mock_handler_in_task_service: HandlerMockFactory,
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    mock_handler_in_task_service(
        _tasks_service.get_result.__name__,
        side_effect=backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{faker.uuid4()}/result")
    assert response.status == expected_status
