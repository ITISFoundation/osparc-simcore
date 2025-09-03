# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import random
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import ANY

import httpx
import pytest
from celery_library.task_manager import CeleryTaskManager
from faker import Faker
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_webserver.functions import (
    ProjectFunctionJob,
    RegisteredProjectFunctionJob,
)
from models_library.functions import (
    FunctionJobStatus,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJobWithStatus,
    TaskID,
)
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from servicelib.celery.models import TaskFilter, TaskState, TaskStatus, TaskUUID
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server._service_function_jobs import FunctionJobService
from simcore_service_api_server.api.routes import function_jobs_routes
from simcore_service_api_server.api.routes.function_jobs_routes import (
    _JOB_CREATION_TASK_STATUS_PREFIX,
)
from simcore_service_api_server.models.schemas.jobs import JobStatus

_faker = Faker()


async def test_delete_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job", None)

    response = await client.delete(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK


async def test_register_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_project_function_job: ProjectFunctionJob,
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:
    """Test the register_function_job endpoint."""

    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_project_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs",
        json=mock_project_function_job.model_dump(mode="json"),
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_project_function_job
    )


async def test_get_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_project_function_job
    )

    # Now, get the function job
    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_project_function_job
    )


async def test_list_function_jobs(
    client: AsyncClient,
    mock_rabbitmq_rpc_client: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [mock_registered_project_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )
    response = await client.get(f"{API_VTAG}/function_jobs", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_project_function_job
    )


@pytest.mark.parametrize("status_str", ["SUCCESS", "FAILED"])
async def test_list_function_jobs_with_status(
    client: AsyncClient,
    mock_rabbitmq_rpc_client: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
    mocker: MockerFixture,
    status_str: str,
) -> None:
    mock_status = FunctionJobStatus(status=status_str)
    mock_outputs = {"X+Y": 42, "X-Y": 10}
    mock_registered_project_function_job_with_status = (
        RegisteredProjectFunctionJobWithStatus(
            **{
                **mock_registered_project_function_job.model_dump(),
                "status": mock_status,
            }
        )
    )
    mock_handler_in_functions_rpc_interface(
        "list_function_jobs_with_status",
        (
            [mock_registered_project_function_job_with_status for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )

    mock_function_job_outputs = mocker.patch.object(
        FunctionJobService, "function_job_outputs", return_value=mock_outputs
    )
    mock_handler_in_functions_rpc_interface("get_function_job_status", mock_status)
    response = await client.get(
        f"{API_VTAG}/function_jobs?include_status=true", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    returned_function_job = RegisteredProjectFunctionJobWithStatus.model_validate(
        data[0]
    )
    if status_str == "SUCCESS":
        mock_function_job_outputs.assert_called()
        assert returned_function_job.outputs == mock_outputs
    else:
        mock_function_job_outputs.assert_not_called()
        assert returned_function_job.outputs is None

    assert returned_function_job == mock_registered_project_function_job_with_status


async def test_list_function_jobs_with_job_id_filter(
    client: AsyncClient,
    mock_rabbitmq_rpc_client: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str], MockType],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    user_id: UserID,
    product_name: ProductName,
    auth: httpx.BasicAuth,
) -> None:

    PAGE_SIZE = 3
    TOTAL_SIZE = 10

    def mocked_list_function_jobs(offset: int, limit: int):
        start = offset
        end = offset + limit
        items = [
            mock_registered_project_function_job
            for _ in range(start, min(end, TOTAL_SIZE))
        ]
        return items, PageMetaInfoLimitOffset(
            total=TOTAL_SIZE, count=len(items), limit=limit, offset=offset
        )

    mock_list_function_jobs = mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
    )

    mock_list_function_jobs.side_effect = lambda *args, **kwargs: (  # noqa: ARG005
        mocked_list_function_jobs(
            kwargs.get("pagination_offset", 0),
            kwargs.get("pagination_limit", PAGE_SIZE),
        )
    )
    for page in range((TOTAL_SIZE + PAGE_SIZE - 1) // PAGE_SIZE):
        offset = page * PAGE_SIZE
        response = await client.get(
            f"{API_VTAG}/function_jobs",
            params={
                "function_job_ids": [str(mock_registered_project_function_job.uid)],
                "limit": PAGE_SIZE,
                "offset": offset,
            },
            auth=auth,
        )
        mock_list_function_jobs.assert_called_with(
            ANY,  # Dummy rpc client
            filter_by_function_job_ids=[mock_registered_project_function_job.uid],
            filter_by_function_job_collection_id=None,
            filter_by_function_id=None,
            pagination_offset=offset,
            pagination_limit=PAGE_SIZE,
            product_name=product_name,
            user_id=user_id,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["items"]
        assert len(data) == min(PAGE_SIZE, TOTAL_SIZE - offset)
        assert (
            RegisteredProjectFunctionJob.model_validate(data[0])
            == mock_registered_project_function_job
        )


@pytest.mark.parametrize("job_status", ["SUCCESS", "FAILED", "STARTED"])
@pytest.mark.parametrize(
    "project_job_id, job_creation_task_id, celery_task_state",
    [
        (
            ProjectID(_faker.uuid4()),
            TaskID(_faker.uuid4()),
            random.choice(list(TaskState)),  # noqa: S311
        ),
        (None, None, random.choice(list(TaskState))),  # noqa: S311
        (None, TaskID(_faker.uuid4()), random.choice(list(TaskState))),  # noqa: S311
    ],
)
async def test_get_function_job_status(
    app: FastAPI,
    mocked_app_dependencies: None,
    client: AsyncClient,
    mocker: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    mock_registered_project_function: RegisteredProjectFunction,
    mock_method_in_jobs_service: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
    job_status: str,
    project_job_id: ProjectID,
    job_creation_task_id: TaskID | None,
    celery_task_state: TaskState,
) -> None:

    _expected_return_status = (
        status.HTTP_500_INTERNAL_SERVER_ERROR
        if job_status not in ("SUCCESS", "FAILED")
        and (project_job_id is None and job_creation_task_id is None)
        else status.HTTP_200_OK
    )

    def _mock_task_manager(*args, **kwargs) -> CeleryTaskManager:
        async def _get_task_status(
            task_uuid: TaskUUID, task_filter: TaskFilter
        ) -> TaskStatus:
            assert f"{task_uuid}" == job_creation_task_id
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=celery_task_state,
                progress_report=ProgressReport(
                    actual_value=0.5,
                    total=1.0,
                    attempt=1,
                    unit=None,
                    message=ProgressStructuredMessage.model_validate(
                        ProgressStructuredMessage.model_json_schema()["$defs"][
                            "ProgressStructuredMessage"
                        ]["examples"][0]
                    ),
                ),
            )

        obj = mocker.Mock(spec=CeleryTaskManager)
        obj.get_task_status = _get_task_status
        return obj

    mocker.patch.object(function_jobs_routes, "get_task_manager", _mock_task_manager)

    mock_handler_in_functions_rpc_interface(
        "get_function_job",
        mock_registered_project_function_job.model_copy(
            update={
                "user_id": ANY,
                "project_job_id": project_job_id,
                "job_creation_task_id": job_creation_task_id,
            }
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job_status",
        FunctionJobStatus(status=job_status),
    )
    mock_method_in_jobs_service(
        "inspect_study_job",
        JobStatus(
            job_id=uuid.uuid4(),
            submitted_at=datetime.fromisoformat("2023-01-01T00:00:00"),
            started_at=datetime.fromisoformat("2023-01-01T01:00:00"),
            stopped_at=datetime.fromisoformat("2023-01-01T02:00:00"),
            state=RunningState(value=job_status),
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "update_function_job_status",
        FunctionJobStatus(status=job_status),
    )

    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}/status",
        auth=auth,
    )
    assert response.status_code == _expected_return_status
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        if project_job_id is not None or job_status in ("SUCCESS", "FAILED"):
            assert data["status"] == job_status
        else:
            assert (
                data["status"]
                == f"{_JOB_CREATION_TASK_STATUS_PREFIX}{celery_task_state}"
            )


@pytest.mark.parametrize(
    "job_outputs, project_job_id, job_status, expected_output, use_db_cache",
    [
        (None, None, "created", None, True),
        (
            {"X+Y": 42, "X-Y": 10},
            ProjectID(_faker.uuid4()),
            RunningState.FAILED,
            None,
            False,
        ),
        (
            {"X+Y": 42, "X-Y": 10},
            ProjectID(_faker.uuid4()),
            RunningState.SUCCESS,
            {"X+Y": 42, "X-Y": 10},
            True,
        ),
    ],
)
async def test_get_function_job_outputs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    mock_registered_project_function: RegisteredProjectFunction,
    mocked_webserver_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    job_outputs: dict[str, Any] | None,
    project_job_id: ProjectID | None,
    job_status: str,
    expected_output: dict[str, Any] | None,
    use_db_cache: bool,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job",
        mock_registered_project_function_job.model_copy(
            update={
                "user_id": ANY,
                "project_job_id": project_job_id,
                "job_creation_task_id": None,
            }
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )

    if use_db_cache:
        mock_handler_in_functions_rpc_interface("get_function_job_outputs", job_outputs)
    else:
        mock_handler_in_functions_rpc_interface("get_function_job_outputs", None)

    mock_handler_in_functions_rpc_interface(
        "get_function_job_status",
        FunctionJobStatus(status=job_status),
    )

    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}/outputs",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == expected_output
