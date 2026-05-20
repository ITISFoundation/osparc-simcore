# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.rpc.webserver.projects import (
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.typing_mock import HandlerMockFactory
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.v1.projects import ProjectsRpcApi
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.routes.solvers_jobs_read import _BATCH_GET_MAX_IDS
from simcore_service_api_server.models.schemas.jobs import (
    BatchGetJobMetadataResponse,
)
from starlette import status


@pytest.fixture
def mock_handler_in_projects_rpc_interface(
    mocked_webserver_rpc_api: dict[str, MockType],
    mocker: MockerFixture,
) -> HandlerMockFactory:
    """Factory to mock a handler in the ProjectsRpcApi interface"""

    def _create(
        handler_name: str,
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType:
        assert exception is None or side_effect is None

        return mocker.patch.object(
            ProjectsRpcApi,
            handler_name,
            return_value=return_value,
            side_effect=exception or side_effect,
        )

    return _create


@pytest.fixture
def solver_key() -> str:
    return "simcore/services/comp/itis/sleeper"


@pytest.fixture
def solver_version() -> str:
    return "2.0.0"


_FAKE_DATETIME = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def job_ids() -> list[ProjectID]:
    return [ProjectID(f"{'0' * 8}-0000-0000-0000-{i:012d}") for i in range(3)]


async def test_batch_get_jobs_custom_metadata_success(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    solver_key: str,
    solver_version: str,
    job_ids: list[ProjectID],
):
    """Test successful batch get of custom metadata with URL construction."""
    custom_metadata: dict[ProjectID, MetadataDict] = {
        job_ids[0]: {"key1": "value1"},
        job_ids[1]: {"key2": "value2"},
        job_ids[2]: {"key3": "value3"},
    }

    job_parent_resource_name = f"solvers/{solver_key.replace('/', '%2F')}/releases/{solver_version}"

    jobs_page = PageRpcProjectJobRpcGet.create(
        chunk=[
            ProjectJobRpcGet(
                uuid=job_id,
                name=f"job-{i}",
                description=f"Job {i}",
                workbench={},
                created_at=_FAKE_DATETIME,
                modified_at=_FAKE_DATETIME,
                job_parent_resource_name=job_parent_resource_name,
                storage_assets_deleted=False,
            )
            for i, job_id in enumerate(job_ids)
        ],
        total=3,
        limit=50,
        offset=0,
    )

    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        return_value=custom_metadata,
    )
    mock_handler_in_projects_rpc_interface(
        "list_projects_marked_as_jobs",
        return_value=jobs_page,
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in job_ids]},
    )
    assert resp.status_code == status.HTTP_200_OK

    result = BatchGetJobMetadataResponse.model_validate(resp.json())
    assert len(result.items) == 3

    for item in result.items:
        assert item.url is not None
        assert str(item.job_id) in str(item.url)
        assert "metadata" in str(item.url)


async def test_batch_get_jobs_custom_metadata_job_not_found(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    solver_key: str,
    solver_version: str,
    job_ids: list[ProjectID],
):
    """Test 422 when a requested job_id is not found."""
    # Only return metadata for the first job
    custom_metadata: dict[ProjectID, MetadataDict] = {
        job_ids[0]: {"key1": "value1"},
    }

    job_parent_resource_name = f"solvers/{solver_key.replace('/', '%2F')}/releases/{solver_version}"

    # Only return one job from the list
    jobs_page = PageRpcProjectJobRpcGet.create(
        chunk=[
            ProjectJobRpcGet(
                uuid=job_ids[0],
                name="job-0",
                description="Job 0",
                workbench={},
                created_at=_FAKE_DATETIME,
                modified_at=_FAKE_DATETIME,
                job_parent_resource_name=job_parent_resource_name,
                storage_assets_deleted=False,
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )

    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        return_value=custom_metadata,
    )
    mock_handler_in_projects_rpc_interface(
        "list_projects_marked_as_jobs",
        return_value=jobs_page,
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in job_ids]},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Jobs not found" in resp.json()["errors"][0]


async def test_batch_get_jobs_custom_metadata_non_solver_job(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    solver_key: str,
    solver_version: str,
    job_ids: list[ProjectID],
):
    """Test 422 when a job is not a solver job (e.g. a study)."""
    custom_metadata: dict[ProjectID, MetadataDict] = {
        job_ids[0]: {"key1": "value1"},
    }

    # Use a study resource name instead of a solver resource name
    study_resource_name = f"studies/{uuid4()}"

    jobs_page = PageRpcProjectJobRpcGet.create(
        chunk=[
            ProjectJobRpcGet(
                uuid=job_ids[0],
                name="job-0",
                description="Job 0",
                workbench={},
                created_at=_FAKE_DATETIME,
                modified_at=_FAKE_DATETIME,
                job_parent_resource_name=study_resource_name,
                storage_assets_deleted=False,
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )

    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        return_value=custom_metadata,
    )
    mock_handler_in_projects_rpc_interface(
        "list_projects_marked_as_jobs",
        return_value=jobs_page,
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(job_ids[0])]},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "not a solver job" in resp.json()["errors"][0]


async def test_batch_get_jobs_custom_metadata_rpc_project_not_found(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    job_ids: list[ProjectID],
):
    """Test that ProjectNotFoundRpcError from the RPC layer is mapped to 404."""
    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        exception=ProjectNotFoundRpcError(),
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in job_ids]},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_batch_get_jobs_custom_metadata_rpc_project_forbidden(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    job_ids: list[ProjectID],
):
    """Test that ProjectForbiddenRpcError from the RPC layer is mapped to 403."""
    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        exception=ProjectForbiddenRpcError(),
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in job_ids]},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_batch_get_jobs_custom_metadata_max_ids(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mock_handler_in_projects_rpc_interface: HandlerMockFactory,
    solver_key: str,
    solver_version: str,
):
    """Test that the endpoint accepts up to _BATCH_GET_MAX_IDS job ids."""
    max_job_ids = [uuid4() for _ in range(_BATCH_GET_MAX_IDS)]
    job_parent_resource_name = f"solvers/{solver_key.replace('/', '%2F')}/releases/{solver_version}"

    custom_metadata: dict[ProjectID, MetadataDict] = {job_id: {"key": "value"} for job_id in max_job_ids}
    jobs_page = PageRpcProjectJobRpcGet.create(
        chunk=[
            ProjectJobRpcGet(
                uuid=job_id,
                name=f"job-{i}",
                description=f"Job {i}",
                workbench={},
                created_at=_FAKE_DATETIME,
                modified_at=_FAKE_DATETIME,
                job_parent_resource_name=job_parent_resource_name,
                storage_assets_deleted=False,
            )
            for i, job_id in enumerate(max_job_ids)
        ],
        total=_BATCH_GET_MAX_IDS,
        limit=_BATCH_GET_MAX_IDS,
        offset=0,
    )

    mock_handler_in_projects_rpc_interface(
        "batch_get_project_custom_metadata",
        return_value=custom_metadata,
    )
    mock_handler_in_projects_rpc_interface(
        "list_projects_marked_as_jobs",
        return_value=jobs_page,
    )

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in max_job_ids]},
    )
    assert resp.status_code == status.HTTP_200_OK
    result = BatchGetJobMetadataResponse.model_validate(resp.json())
    assert len(result.items) == _BATCH_GET_MAX_IDS


async def test_batch_get_jobs_custom_metadata_exceeds_max_ids(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    """Test that the endpoint returns 422 when more than _BATCH_GET_MAX_IDS job ids are passed."""
    too_many_job_ids = [uuid4() for _ in range(_BATCH_GET_MAX_IDS + 1)]

    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs/metadata:batchGet",
        auth=auth,
        params={"job_ids": [str(j) for j in too_many_job_ids]},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
