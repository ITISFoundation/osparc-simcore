# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import NamedTuple

import httpx
import pytest
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.jobs import Job
from starlette import status


class MockBackendRouters(NamedTuple):
    webserver_rest: MockRouter
    webserver_rpc: dict[str, MockType]
    catalog_rpc: dict[str, MockType]


@pytest.fixture
def mocked_backend(
    mocked_webserver_rest_api_base: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    mocked_catalog_rpc_api: dict[str, MockType],
    project_tests_dir: Path,
) -> MockBackendRouters:
    mock_name = "on_list_jobs.json"
    captures = TypeAdapter(list[HttpApiCallCaptureModel]).validate_json(
        Path(project_tests_dir / "mocks" / mock_name).read_text()
    )

    capture = captures[1]
    assert capture.host == "webserver"
    assert capture.name == "list_projects"
    mocked_webserver_rest_api_base.request(
        method=capture.method,
        name=capture.name,
        path=capture.path,
    ).respond(
        status_code=capture.status_code,
        json=capture.response_body,
    )

    return MockBackendRouters(
        webserver_rest=mocked_webserver_rest_api_base,
        webserver_rpc=mocked_webserver_rpc_api,
        catalog_rpc=mocked_catalog_rpc_api,
    )


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/issues/4110"
)
async def test_list_solver_jobs(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_backend: MockBackendRouters,
):
    # list jobs (w/o pagination)
    resp = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs", auth=auth
    )
    assert resp.status_code == status.HTTP_200_OK
    jobs = TypeAdapter(list[Job]).validate_python(resp.json())

    # list jobs (w/ pagination)
    resp = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/page",
        auth=auth,
        params={"limits": 20},
    )
    assert resp.status_code == status.HTTP_200_OK

    jobs_page = TypeAdapter(Page[Job]).validate_python(resp.json())

    assert jobs_page.items == jobs

    # check calls to the deep-backend services
    assert mocked_backend.webserver_rest["list_projects"].called
    assert mocked_backend.catalog_rpc["get_service"].called


async def test_list_all_solvers_jobs(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mocked_backend: MockBackendRouters,
):
    """Tests the endpoint that lists all jobs across all solvers."""

    # Call the endpoint with pagination parameters
    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs",
        auth=auth,
        params={"limit": 10, "offset": 0},
    )

    # Verify the response
    assert resp.status_code == status.HTTP_200_OK

    # Parse and validate the response
    jobs_page = TypeAdapter(Page[Job]).validate_python(resp.json())

    # Basic assertions on the response structure
    assert isinstance(jobs_page.items, list)
    assert jobs_page.total > 0
    assert jobs_page.limit == 10
    assert jobs_page.offset == 0
    assert jobs_page.total <= len(jobs_page.items)

    # Each job should have the expected structure
    for job in jobs_page.items:
        assert job.id
        assert job.name
        assert job.url is not None
        assert job.runner_url is not None
        assert job.outputs_url is not None

    assert mocked_backend.webserver_rpc["list_projects_marked_as_jobs"].called


async def test_list_all_solvers_jobs_with_metadata_filter(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    mocked_backend: MockBackendRouters,
    user_id: UserID,
):
    """Tests the endpoint that lists all jobs across all solvers with metadata filtering."""

    # Test with metadata filters
    metadata_filters = ["key1:val*", "key2:exactval"]

    # Construct query parameters with metadata.any filters
    params = {
        "limit": 10,
        "offset": 0,
        "metadata.any": metadata_filters,
    }

    # Call the endpoint with metadata filters
    resp = await client.get(
        f"/{API_VTAG}/solvers/-/releases/-/jobs",
        auth=auth,
        params=params,
    )

    # Verify the response
    assert resp.status_code == status.HTTP_200_OK

    # Parse and validate the response
    jobs_page = TypeAdapter(Page[Job]).validate_python(resp.json())

    # Basic assertions on the response structure
    assert isinstance(jobs_page.items, list)
    assert jobs_page.limit == 10
    assert jobs_page.offset == 0

    # Check that the backend was called with the correct filter parameters
    assert mocked_backend.webserver_rpc["list_projects_marked_as_jobs"].called

    # Get the call args to verify filter parameters were passed correctly
    call_args = mocked_backend.webserver_rpc["list_projects_marked_as_jobs"].call_args

    # The filter_any_custom_metadata parameter should contain our filters
    # The exact structure will depend on how your mocked function is called
    assert call_args is not None

    assert call_args.kwargs["product_name"] == "osparc"
    assert call_args.kwargs["user_id"] == user_id
    assert call_args.kwargs["offset"] == 0
    assert call_args.kwargs["limit"] == 10
    assert call_args.kwargs["filters"]

    # Verify the metadata filters were correctly transformed and passed
    assert call_args.kwargs["filters"].any_custom_metadata[0].name == "key1"
    assert call_args.kwargs["filters"].any_custom_metadata[0].pattern == "val*"
    assert call_args.kwargs["filters"].any_custom_metadata[1].name == "key2"
    assert call_args.kwargs["filters"].any_custom_metadata[1].pattern == "exactval"
