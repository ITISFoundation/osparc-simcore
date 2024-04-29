# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import TypedDict

import httpx
import jinja2
import pytest
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from pydantic import parse_file_as
from pytest_simcore.helpers.httpx_calls_capture_model import HttpApiCallCaptureModel
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from starlette import status


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend_services_apis_for_delete_non_existing_project(
    mocked_webserver_service_api: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "delete_project_not_found.json"
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(project_tests_dir / "mocks"), autoescape=True
    )
    template = environment.get_template(mock_name)

    def _response(request: httpx.Request, project_id: str):
        capture = HttpApiCallCaptureModel.parse_raw(
            template.render(project_id=project_id)
        )
        return httpx.Response(
            status_code=capture.status_code, json=capture.response_body
        )

    mocked_webserver_service_api.delete(
        path__regex=rf"/projects/(?P<project_id>{UUID_RE_BASE})$",
        name="delete_project",
    ).mock(side_effect=_response)

    return MockedBackendApiDict(webserver=mocked_webserver_service_api, catalog=None)


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4111"
)
async def test_delete_non_existing_solver_job(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    faker: Faker,
    mocked_backend_services_apis_for_delete_non_existing_project: MockedBackendApiDict,
):
    # Cannot delete if it does not exists
    resp = await client.delete(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{faker.uuid4()}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    mock_webserver_router = (
        mocked_backend_services_apis_for_delete_non_existing_project["webserver"]
    )
    assert mock_webserver_router
    assert mock_webserver_router["delete_project"].called


@pytest.fixture
def mocked_backend_services_apis_for_create_and_delete_solver_job(
    mocked_webserver_service_api: MockRouter,
    mocked_catalog_service_api: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "on_create_job.json"

    # fixture
    captures = parse_file_as(
        list[HttpApiCallCaptureModel],
        project_tests_dir / "mocks" / mock_name,
    )

    capture = captures[0]
    assert capture.host == "catalog"
    assert capture.method == "GET"
    mocked_catalog_service_api.request(
        method=capture.method, path=capture.path, name="get_service"  # GET service
    ).respond(status_code=capture.status_code, json=capture.response_body)

    capture = captures[-1]
    assert capture.host == "webserver"
    assert capture.method == "DELETE"

    mocked_webserver_service_api.delete(
        path__regex=rf"/projects/(?P<project_id>{UUID_RE_BASE})$",
        name="delete_project",
    ).respond(status_code=capture.status_code, json=capture.response_body)

    return MockedBackendApiDict(
        catalog=mocked_catalog_service_api,
        webserver=mocked_webserver_service_api,
    )


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4111"
)
async def test_create_and_delete_solver_job(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_backend_services_apis_for_create_and_delete_solver_job: MockedBackendApiDict,
):
    # create Job
    resp = await client.post(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        json=JobInputs(
            values={
                "x": 3.14,
                "n": 42,
            }
        ).dict(),
    )
    assert resp.status_code == status.HTTP_201_CREATED
    job = Job.parse_obj(resp.json())

    # Delete Job after creation
    resp = await client.delete(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    mock_webserver_router = (
        mocked_backend_services_apis_for_create_and_delete_solver_job["webserver"]
    )
    assert mock_webserver_router
    assert mock_webserver_router["delete_project"].called

    mock_catalog_router = mocked_backend_services_apis_for_create_and_delete_solver_job[
        "catalog"
    ]
    assert mock_catalog_router
    assert mock_catalog_router["get_service"].called

    # NOTE: ideas for further tests
    # Run job and try to delete while running
    # Run a job and delete when finished
