# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import httpx
import pytest
import respx
from pytest_mock import MockerFixture
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import (
    JobMetadata,
    JobMetadataUpdate,
)
from simcore_service_api_server.models.schemas.studies import StudyID
from starlette import status
from unit.conftest import SideEffectCallback


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
    project_tests_dir: Path,
    mocked_webserver_service_api_base: MockRouter,
    mocked_catalog_service_api_base: MockRouter,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]],
        list[respx.MockRouter],
    ],
    mocker: MockerFixture,
) -> MockedBackendApiDict | None:
    respx_mock_from_capture(
        [
            mocked_webserver_service_api_base,
            mocked_catalog_service_api_base,
        ],
        project_tests_dir / "mocks" / "test_get_and_update_study_job_metadata.json",
        [],
    )

    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api_base,
        catalog=mocked_catalog_service_api_base,
    )


async def test_get_and_update_study_job_metadata(
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    study_id: StudyID,
    mocked_backend: MockedBackendApiDict,
):
    job_id = "4e7114e9-9cc4-43b8-bbfc-e32d1e4817ac"

    # Get metadata
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.parse_obj(resp.json())

    assert job_meta.metadata == {}

    # Update metadata
    my_metadata = {
        "number": 3.14,
        "integer": 42,
        "string": "foo",
        "boolean": True,
    }
    resp = await client.patch(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
        json=JobMetadataUpdate(metadata=my_metadata).dict(),
    )
    assert resp.status_code == status.HTTP_200_OK

    job_meta = JobMetadata.parse_obj(resp.json())
    assert job_meta.metadata == my_metadata

    # Get metadata after update
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
    job_meta = JobMetadata.parse_obj(resp.json())

    assert job_meta.metadata == my_metadata

    # Delete job
    resp = await client.delete(
        f"/v0/studies/{study_id}/jobs/{job_id}",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Get metadata -> job not found!
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    mock_webserver_router = mocked_backend["webserver"]
    assert mock_webserver_router
    assert mock_webserver_router["get_project_metadata"].called
    assert mock_webserver_router["update_project_metadata"].called
    assert mock_webserver_router["delete_project"].called
