# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import TypedDict

import httpx
import pytest
from pydantic import parse_file_as, parse_obj_as
from respx import MockRouter
from simcore_service_api_server.models.pagination import LimitOffsetPage
from simcore_service_api_server.models.schemas.jobs import Job
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from starlette import status


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def solver_key() -> str:
    return "simcore/services/comp/itis/sleeper"


@pytest.fixture
def solver_version() -> str:
    return "2.0.0"


@pytest.fixture
def mocked_backend_services_apis_to_read_solver_jobs(
    mocked_webserver_service_api_base: MockRouter,
    mocked_catalog_service_api_base: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "on_list_jobs.json"

    # fixture
    captures = parse_file_as(
        list[HttpApiCallCaptureModel],
        project_tests_dir / "mocks" / mock_name,
    )

    capture = captures[0]
    assert capture.host == "catalog"
    assert capture.method == "GET"
    mocked_catalog_service_api_base.request(
        method=capture.method, path=capture.path, name="get_services"
    ).respond(status_code=capture.status_code, json=capture.response_body)

    capture = captures[1]
    assert capture.host == "webserver"
    assert capture.method == "GET"
    assert capture.name == "list_projects"
    mocked_webserver_service_api_base.request(
        method=capture.method,
        path=capture.path,
        name=capture.name,
        params__contains={
            "show_hidden": "true",
            "offset": "0",
            "search": "solvers%2Fsimcore%252Fservices%252Fcomp%252Fitis%252Fsleeper%2Freleases%2F2.0.0",
        },
    ).respond(status_code=capture.status_code, json=capture.response_body)

    return MockedBackendApiDict(
        catalog=mocked_catalog_service_api_base,
        webserver=mocked_webserver_service_api_base,
    )


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/issues/4110"
)
async def test_list_solver_jobs(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_backend_services_apis_to_read_solver_jobs: MockedBackendApiDict,
):

    # list jobs (w/o pagination)
    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs", auth=auth
    )
    assert resp.status_code == status.HTTP_200_OK
    jobs = parse_obj_as(list[Job], resp.json())

    # list jobs (w/ pagination)
    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        params={"limits": 20},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    jobs_page = parse_obj_as(LimitOffsetPage[Job], resp.json())

    assert jobs_page.items == jobs

    # check calls to the deep-backend services
    mock_webserver_router = mocked_backend_services_apis_to_read_solver_jobs[
        "webserver"
    ]
    assert mock_webserver_router
    assert mock_webserver_router["list_projects"].called

    mock_catalog_router = mocked_backend_services_apis_to_read_solver_jobs["catalog"]
    assert mock_catalog_router
    assert mock_catalog_router["get_service"].called
