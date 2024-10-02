# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from pathlib import Path
from typing import TypedDict

import httpx
import pytest
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from pydantic import TypeAdapter
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
)
from starlette import status


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


def _as_path_regex(initial_path: str):
    return (
        re.sub(rf"({UUID_RE_BASE})", f"(?P<project_id>{UUID_RE_BASE})", initial_path)
        + "$"
    )


@pytest.fixture
def mocked_backend(
    mocked_webserver_service_api: MockRouter,
    mocked_catalog_service_api: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "for_test_get_and_update_job_metadata.json"

    captures = {
        c.name: c
        for c in TypeAdapter(list[HttpApiCallCaptureModel]).validate_json(
            Path(project_tests_dir / "mocks" / mock_name).read_text()
        )
    }

    capture = captures["get_service"]
    assert capture.host == "catalog"
    mocked_catalog_service_api.request(
        method=capture.method,
        path=capture.path,
        name=capture.name,
    ).respond(
        status_code=capture.status_code,
        json=capture.response_body,
    )

    for name in ("get_project_metadata", "update_project_metadata", "delete_project"):
        capture = captures[name]
        assert capture.host == "webserver"
        capture_path_regex = _as_path_regex(capture.path.removeprefix("/v0"))

        route = mocked_webserver_service_api.request(
            method=capture.method,
            path__regex=capture_path_regex,
            name=capture.name,
        )

        if name == "get_project_metadata":
            # SEE https://lundberg.github.io/respx/guide/#iterable
            route.side_effect = [
                captures["get_project_metadata"].as_response(),
                captures["get_project_metadata_1"].as_response(),
                captures["get_project_metadata_2"].as_response(),
            ]
        else:
            route.respond(
                status_code=capture.status_code,
                json=capture.response_body,
            )

    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api, catalog=mocked_catalog_service_api
    )


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
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        json=JobInputs(
            values={
                "x": 4.33,
                "n": 55,
                "title": "Temperature",
                "enabled": True,
            }
        ).model_dump(),
    )
    assert resp.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(resp.json())

    # Get metadata
    resp = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.model_validate(resp.json())

    assert job_meta.metadata == {}

    # Update metadata
    my_metadata = {"number": 3.14, "integer": 42, "string": "foo", "boolean": True}
    resp = await client.patch(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
        json=JobMetadataUpdate(metadata=my_metadata).model_dump(),
    )
    assert resp.status_code == status.HTTP_200_OK

    job_meta = JobMetadata.model_validate(resp.json())
    assert job_meta.metadata == my_metadata

    # Get metadata after update
    resp = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.model_validate(resp.json())

    assert job_meta.metadata == my_metadata

    # Delete job
    resp = await client.delete(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Get metadata -> job not found!
    resp = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    mock_webserver_router = mocked_backend["webserver"]
    assert mock_webserver_router
    assert mock_webserver_router["get_project_metadata"].called
    assert mock_webserver_router["update_project_metadata"].called
    assert mock_webserver_router["delete_project"].called
