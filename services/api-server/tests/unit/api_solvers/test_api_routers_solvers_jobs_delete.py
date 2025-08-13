# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import TypedDict
from uuid import UUID

import httpx
import jinja2
import pytest
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from pydantic import TypeAdapter
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from respx import MockRouter
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from starlette import status

_faker = Faker()


class MockedBackendApiDict(TypedDict):
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend_services_apis_for_delete_non_existing_project(
    mocked_webserver_rest_api: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "delete_project_not_found.json"
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(project_tests_dir / "mocks"), autoescape=True
    )
    template = environment.get_template(mock_name)

    def _response(request: httpx.Request, project_id: str):
        capture = HttpApiCallCaptureModel.model_validate_json(
            template.render(project_id=project_id)
        )
        return httpx.Response(
            status_code=capture.status_code, json=capture.response_body
        )

    mocked_webserver_rest_api.delete(
        path__regex=rf"/projects/(?P<project_id>{UUID_RE_BASE})$",
        name="delete_project",
    ).mock(side_effect=_response)

    return MockedBackendApiDict(webserver=mocked_webserver_rest_api)


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
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{faker.uuid4()}",
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
    mocked_webserver_rest_api: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "on_create_job.json"

    # fixture
    captures = TypeAdapter(list[HttpApiCallCaptureModel]).validate_json(
        Path(project_tests_dir / "mocks" / mock_name).read_text()
    )

    # capture = captures[0]
    # assert capture.host == "catalog"
    # assert capture.method == "GET"
    # mocked_catalog_rest_api.request(
    #     method=capture.method, path=capture.path, name="get_service"  # GET service
    # ).respond(status_code=capture.status_code, json=capture.response_body)

    capture = captures[-1]
    assert capture.host == "webserver"
    assert capture.method == "DELETE"

    mocked_webserver_rest_api.delete(
        path__regex=rf"/projects/(?P<project_id>{UUID_RE_BASE})$",
        name="delete_project",
    ).respond(status_code=capture.status_code, json=capture.response_body)

    return MockedBackendApiDict(
        webserver=mocked_webserver_rest_api,
    )


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4111"
)
async def test_create_and_delete_solver_job(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_catalog_rpc_api: dict[str, MockType],
    mocked_backend_services_apis_for_create_and_delete_solver_job: MockedBackendApiDict,
):
    # create Job
    resp = await client.post(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        json=JobInputs(
            values={
                "x": 3.14,
                "n": 42,
            }
        ).model_dump(),
    )
    assert resp.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(resp.json())

    # Delete Job after creation
    resp = await client.delete(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    mock_webserver_router = (
        mocked_backend_services_apis_for_create_and_delete_solver_job["webserver"]
    )
    assert mock_webserver_router
    assert mock_webserver_router["delete_project"].called

    get_service = mocked_catalog_rpc_api["get_service"]
    assert get_service
    assert get_service.called

    # NOTE: ideas for further tests
    # Run job and try to delete while running
    # Run a job and delete when finished


@pytest.mark.parametrize(
    "parent_node_id, parent_project_id",
    [(_faker.uuid4(), _faker.uuid4()), (None, None)],
)
@pytest.mark.parametrize("hidden", [True, False])
async def test_create_job(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_backend_services_apis_for_create_and_delete_solver_job: MockedBackendApiDict,
    mocked_catalog_rpc_api: dict[str, MockType],
    hidden: bool,
    parent_project_id: UUID | None,
    parent_node_id: UUID | None,
):

    mock_webserver_router = (
        mocked_backend_services_apis_for_create_and_delete_solver_job["webserver"]
    )
    assert mock_webserver_router is not None
    callback = mock_webserver_router["create_projects"].side_effect
    assert callback is not None

    def create_project_side_effect(request: httpx.Request):
        # check `hidden` bool
        query = dict(elm.split("=") for elm in request.url.query.decode().split("&"))
        _hidden = query.get("hidden")
        assert _hidden == ("true" if hidden else "false")

        # check parent project and node id
        if parent_project_id is not None:
            assert f"{parent_project_id}" == dict(request.headers).get(
                X_SIMCORE_PARENT_PROJECT_UUID.lower()
            )
        if parent_node_id is not None:
            assert f"{parent_node_id}" == dict(request.headers).get(
                X_SIMCORE_PARENT_NODE_ID.lower()
            )
        return callback(request)

    mock_webserver_router["create_projects"].side_effect = create_project_side_effect

    # create Job
    header_dict = {}
    if parent_project_id is not None:
        header_dict[X_SIMCORE_PARENT_PROJECT_UUID] = f"{parent_project_id}"
    if parent_node_id is not None:
        header_dict[X_SIMCORE_PARENT_NODE_ID] = f"{parent_node_id}"
    resp = await client.post(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        params={"hidden": f"{hidden}"},
        headers=header_dict,
        json=JobInputs(
            values={
                "x": 3.14,
                "n": 42,
            }
        ).model_dump(),
    )
    assert resp.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(resp.json())


@pytest.fixture
def mocked_backend_services_apis_for_delete_job_assets(
    mocked_webserver_rest_api: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    mocked_storage_rest_api_base: MockRouter,
) -> dict[str, MockRouter | dict[str, MockType]]:

    # Patch PATCH /projects/{project_id}
    def _patch_project(request: httpx.Request, **kwargs):
        # Accept any patch, return 204 No Content
        return httpx.Response(status_code=status.HTTP_204_NO_CONTENT)

    mocked_webserver_rest_api.patch(
        path__regex=r"/projects/(?P<project_id>[\w-]+)$",
        name="patch_project",
    ).mock(side_effect=_patch_project)

    # Mock storage REST delete_project_s3_assets
    def _delete_project_s3_assets(request: httpx.Request, **kwargs):
        return httpx.Response(status_code=status.HTTP_204_NO_CONTENT)

    mocked_storage_rest_api_base.delete(
        path__regex=r"/simcore-s3/folders/(?P<project_id>[\w-]+)$",
        name="delete_project_s3_assets",
    ).mock(side_effect=_delete_project_s3_assets)

    return {
        "webserver_rest": mocked_webserver_rest_api,
        "webserver_rpc": mocked_webserver_rpc_api,
        "storage_rest": mocked_storage_rest_api_base,
    }


@pytest.mark.acceptance_test("Test delete_job_assets endpoint")
async def test_delete_job_assets_endpoint(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    mocked_backend_services_apis_for_delete_job_assets: dict[
        str, MockRouter | dict[str, MockType]
    ],
):
    job_id = "123e4567-e89b-12d3-a456-426614174000"
    url = f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/assets"

    resp = await client.delete(url, auth=auth)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    webserver_rest = mocked_backend_services_apis_for_delete_job_assets[
        "webserver_rest"
    ]
    assert webserver_rest["patch_project"].called

    storage_rest = mocked_backend_services_apis_for_delete_job_assets["storage_rest"]
    assert storage_rest["delete_project_s3_assets"].called

    webserver_rpc = mocked_backend_services_apis_for_delete_job_assets["webserver_rpc"]
    assert webserver_rpc["mark_project_as_job"].called
