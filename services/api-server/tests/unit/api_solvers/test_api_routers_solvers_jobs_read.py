# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import NamedTuple

import httpx
import pytest
from pydantic import TypeAdapter
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.jobs import Job
from starlette import status


class MockBackendRouters(NamedTuple):
    webserver: MockRouter
    catalog: dict[str, MockType]


@pytest.fixture
def mocked_backend(
    mocked_webserver_rest_api_base: MockRouter,
    mocked_rpc_catalog_service_api: dict[str, MockType],
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
        webserver=mocked_webserver_rest_api_base,
        catalog=mocked_rpc_catalog_service_api,
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
    assert mocked_backend.webserver["list_projects"].called
    assert mocked_backend.catalog["get_service"].called
