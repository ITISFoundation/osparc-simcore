# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path
from typing import TypedDict

import httpx
import pytest
from fastapi.encoders import jsonable_encoder
from pytest_simcore.helpers.httpx_calls_capture_models import CreateRespxMockCallback
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobMetadata,
    JobMetadataUpdate,
)
from simcore_service_api_server.models.schemas.studies import StudyID
from starlette import status


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
    project_tests_dir: Path,
    mocked_webserver_service_api_base: MockRouter,
    mocked_catalog_service_api_base: MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
) -> MockedBackendApiDict | None:
    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_service_api_base,
            mocked_catalog_service_api_base,
        ],
        capture_path=project_tests_dir
        / "mocks"
        / "test_get_and_update_study_job_metadata.json",
        side_effects_callbacks=[],
    )

    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api_base,
        catalog=mocked_catalog_service_api_base,
    )


@pytest.fixture
def study_id() -> StudyID:
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
