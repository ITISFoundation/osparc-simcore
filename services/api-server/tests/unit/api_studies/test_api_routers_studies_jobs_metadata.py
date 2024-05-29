# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path
from typing import TypedDict

import httpx
import pytest
from fastapi.encoders import jsonable_encoder
from pydantic import parse_file_as
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from pytest_simcore.helpers.httpx_calls_capture_parameters import PathDescription
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobMetadata,
    JobMetadataUpdate,
)
from simcore_service_api_server.models.schemas.studies import StudyID
from starlette import status


class MockedBackendApiDict(TypedDict):
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
    project_tests_dir: Path,
    mocked_webserver_service_api_base: MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
) -> MockedBackendApiDict | None:
    # load
    captures = {
        c.name: c
        for c in parse_file_as(
            list[HttpApiCallCaptureModel],
            project_tests_dir / "mocks" / "test_get_and_update_study_job_metadata.json",
        )
    }

    # mock every entry
    for name in [
        "create_project",
        "get_task_status",
        "get_task_result",
        "get_project",
        "replace_project",
        "get_project_inputs",
        "update_project_metadata",
        "delete_project",
    ]:
        c = captures[name]
        assert isinstance(c.path, PathDescription)
        mocked_webserver_service_api_base.request(
            method=c.method.upper(),
            url=None,
            path__regex=f"^{c.path.to_path_regex()}$",
            name=name,
        ).mock(return_value=c.as_response())

    # mock this entrypoint using https://lundberg.github.io/respx/guide/#iterable
    c1 = captures["get_project_metadata"]
    assert isinstance(c1.path, PathDescription)
    c2 = captures["get_project_metadata_2"]
    c3 = captures["get_project_metadata_3"]
    mocked_webserver_service_api_base.request(
        method=c.method.upper(),
        url=None,
        path__regex=f"^{c1.path.to_path_regex()}$",
        name="get_project_metadata",
    ).mock(
        side_effect=[
            c1.as_response(),
            c2.as_response(),
        ],
        return_value=c3.as_response(),
    )

    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api_base,
    )


@pytest.fixture
def study_id() -> StudyID:
    # NOTE: this id is used in  mocks/test_get_and_update_study_job_metadata.json
    return StudyID("6377d922-fcd7-11ee-b4fc-0242ac140024")


async def test_get_and_update_study_job_metadata(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    study_id: StudyID,
    mocked_backend: MockedBackendApiDict,
):
    # Creates a job (w/o running it)
    resp = await client.post(
        f"/v0/studies/{study_id}/jobs",
        auth=auth,
        json={"values": {}},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    job = Job(**resp.json())

    # Get metadata
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata(**resp.json())

    assert job_meta.metadata == {}

    # Update metadata
    my_metadata = {
        "number": 3.14,
        "integer": 42,
        "string": "foo",
        "boolean": True,
    }
    resp = await client.put(
        f"/v0/studies/{study_id}/jobs/{job.id}/metadata",
        auth=auth,
        json=jsonable_encoder(JobMetadataUpdate(metadata=my_metadata)),
    )
    assert resp.status_code == status.HTTP_200_OK

    job_meta = JobMetadata(**resp.json())
    assert job_meta.metadata == my_metadata

    # Get metadata after update
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata(**resp.json())

    assert job_meta.metadata == my_metadata

    # Delete job
    resp = await client.delete(
        f"/v0/studies/{study_id}/jobs/{job.id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Get metadata -> job not found!
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job.id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
