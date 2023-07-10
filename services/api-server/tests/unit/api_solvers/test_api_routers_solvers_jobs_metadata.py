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
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
)
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from starlette import status


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
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
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4110"
)
async def test_get_and_update_job_metadata(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    faker: Faker,
    mocked_backend: MockedBackendApiDict,
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
    assert resp.status_code == status.HTTP_200_OK
    job = Job.parse_obj(resp.json())

    # Get metadata
    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.parse_obj(resp.json())

    assert job_meta.metadata == {}

    # Update metadata
    my_metadata = {"number": 3.14, "integer": 42, "string": "foo", "boolean": True}
    resp = await client.patch(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
        json=JobMetadataUpdate(metadata=my_metadata).dict(),
    )
    assert resp.status_code == status.HTTP_200_OK

    job_meta = JobMetadata.parse_obj(resp.json())
    assert job_meta.metadata == my_metadata

    # Get metadata after update
    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.parse_obj(resp.json())

    assert job_meta.metadata == my_metadata

    # Delete job
    resp = await client.delete(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Get metadata -> job not found!
    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    mock_webserver_router = mocked_backend["webserver"]
    assert mock_webserver_router
    assert mock_webserver_router["get_project_metadata"].called
    assert mock_webserver_router["update_project_metadata"].called
    assert mock_webserver_router["delete_project"].called
