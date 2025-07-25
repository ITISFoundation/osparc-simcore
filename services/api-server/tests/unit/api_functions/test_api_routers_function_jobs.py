# pylint: disable=unused-argument

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from models_library.api_schemas_webserver.functions import (
    ProjectFunctionJob,
    RegisteredProjectFunctionJob,
)
from models_library.functions import FunctionJobStatus, RegisteredProjectFunction
from models_library.projects_state import RunningState
from models_library.rest_pagination import PageMetaInfoLimitOffset
from servicelib.aiohttp import status
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import JobStatus


async def test_delete_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job", None)

    # Now, delete the function job
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

    # Now, list function jobs
    response = await client.get(f"{API_VTAG}/function_jobs", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_project_function_job
    )


@pytest.mark.parametrize("job_status", ["SUCCESS", "FAILED", "STARTED"])
async def test_get_function_job_status(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    mock_registered_project_function: RegisteredProjectFunction,
    mock_handler_in_study_jobs_rest_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
    job_status: str,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job_status",
        FunctionJobStatus(status=job_status),
    )
    mock_handler_in_study_jobs_rest_interface(
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
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == job_status


@pytest.mark.parametrize("job_outputs", [{"X+Y": 42, "X-Y": 10}])
async def test_get_function_job_outputs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
    job_outputs: dict[str, Any],
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface("get_function_job_outputs", job_outputs)

    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}/outputs",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == job_outputs
