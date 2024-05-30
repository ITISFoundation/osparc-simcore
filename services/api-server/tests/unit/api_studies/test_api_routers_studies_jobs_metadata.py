# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import re
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

    # group captures
    names = list(captures)
    groups = {}
    used = set()
    for n, name in enumerate(names):
        group = (
            [other for other in names[n:] if re.match(rf"{name}_\d+$", other)]
            if name not in used
            else []
        )
        if name not in used:
            groups[name] = group
        used.update(group)

    assert groups == {
        "clone_project": [],
        "get_clone_project_task_status": [
            "get_clone_project_task_status_1",
            "get_clone_project_task_status_2",
            "get_clone_project_task_status_3",
            "get_clone_project_task_status_4",
        ],
        "get_clone_project_task_result": [],
        "patch_project": [],
        "get_project_inputs": [],
        "get_project_metadata": ["get_project_metadata_1", "get_project_metadata_2"],
        "patch_project_metadata": [],
        "delete_project": [],
    }

    # setup mocks
    for name, group in groups.items():
        c = captures[name]
        assert isinstance(c.path, PathDescription)
        if group:
            # mock this entrypoint using https://lundberg.github.io/respx/guide/#iterable
            cc = [c] + [captures[_] for _ in group]
            mocked_webserver_service_api_base.request(
                method=c.method.upper(),
                url=None,
                path__regex=f"^{c.path.to_path_regex()}$",
                name=name,
            ).mock(
                side_effect=[_.as_response() for _ in cc[:-1]],
                return_value=cc[-1].as_response(),
            )
        else:
            mocked_webserver_service_api_base.request(
                method=c.method.upper(),
                url=None,
                path__regex=f"^{c.path.to_path_regex()}$",
                name=name,
            ).mock(return_value=c.as_response())

    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api_base,
    )


@pytest.fixture
def study_id() -> StudyID:
    # NOTE: this id is used in  mocks/test_get_and_update_study_job_metadata.json
    return StudyID("784f63f4-1d9f-11ef-892d-0242ac140012")


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
    assert resp.status_code == status.HTTP_200_OK
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
