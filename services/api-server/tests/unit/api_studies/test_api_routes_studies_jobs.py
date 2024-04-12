# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import httpx
import pytest
import respx
from faker import Faker
from fastapi import status
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobOutputs
from simcore_service_api_server.models.schemas.studies import Study, StudyID
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from unit.conftest import SideEffectCallback


@pytest.mark.xfail(reason="Still not implemented")
@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4177"
)
async def test_studies_jobs_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api_base: respx.MockRouter,
    study_id: StudyID,
):
    # get_study
    resp = await client.get("/v0/studies/{study_id}", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    study = parse_obj_as(Study, resp.json())
    assert study.uid == study_id

    # Lists study jobs
    resp = await client.get("/v0/studies/{study_id}/jobs", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Create Study Job
    resp = await client.post("/v0/studies/{study_id}/jobs", auth=auth)
    assert resp.status_code == status.HTTP_201_CREATED

    job = parse_obj_as(Job, resp.json())
    job_id = job.id

    # Get Study Job
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Start Study Job
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}:start", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Inspect Study Job
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}:inspect", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Get Study Job Outputs
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}/outputs", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Get Study Job Outputs Logfile
    resp = await client.get(
        f"/v0/studies/{study_id}/jobs/{job_id}/outputs/logfile", auth=auth
    )
    assert resp.status_code == status.HTTP_200_OK

    # Verify that the Study Job already finished and therefore is stopped
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}:stop", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Delete Study Job
    resp = await client.delete(f"/v0/studies/{study_id}/jobs/{job_id}", auth=auth)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify that Study Job is deleted
    resp = await client.delete(f"/v0/studies/{study_id}/jobs/{job_id}", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # job metadata
    resp = await client.get(f"/v0/studies/{study_id}/jobs/{job_id}/metadata", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["metadata"] == {}

    # update_study metadata
    custom_metadata = {"number": 3.14, "string": "str", "boolean": False}
    resp = await client.put(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
        json=custom_metadata,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["metadata"] == custom_metadata

    # other type
    new_metadata = custom_metadata.copy()
    new_metadata["other"] = custom_metadata.copy()  # or use json.dumps
    resp = await client.put(
        f"/v0/studies/{study_id}/jobs/{job_id}/metadata",
        auth=auth,
        json=custom_metadata,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["metadata"]["other"] == str(new_metadata["other"])


async def test_start_stop_delete_study_job(
    client: httpx.AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    fake_study_id: UUID,
    faker: Faker,
):
    capture_file = project_tests_dir / "mocks" / "study_job_start_stop_delete.json"
    job_id = faker.uuid4()

    def _side_effect_no_project_id(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    def _side_effect_with_project_id(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        path_param_job_id = path_params.get("project_id")
        assert path_param_job_id == job_id
        body = capture.response_body
        assert isinstance(body, dict)
        assert body.get("id")
        body["id"] = path_param_job_id
        return body

    respx_mock_from_capture(
        [mocked_webserver_service_api_base, mocked_directorv2_service_api_base],
        capture_file,
        [_side_effect_no_project_id]
        + [_side_effect_with_project_id] * 3
        + [_side_effect_no_project_id],
    )

    def _check_response(response: httpx.Response, status_code: int):
        response.raise_for_status()
        assert response.status_code == status_code
        if response.status_code != status.HTTP_204_NO_CONTENT:
            _response_job_id = response.json().get("job_id")
            assert _response_job_id
            assert _response_job_id == job_id

    # start study job
    response = await client.post(
        f"{API_VTAG}/studies/{fake_study_id}/jobs/{job_id}:start",
        auth=auth,
    )
    _check_response(response, status.HTTP_200_OK)

    # stop study job
    response = await client.post(
        f"{API_VTAG}/studies/{fake_study_id}/jobs/{job_id}:stop",
        auth=auth,
    )
    _check_response(response, status.HTTP_200_OK)

    # delete study job
    response = await client.delete(
        f"{API_VTAG}/studies/{fake_study_id}/jobs/{job_id}",
        auth=auth,
    )
    _check_response(response, status.HTTP_204_NO_CONTENT)


async def test_create_study_job(
    client: httpx.AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    fake_study_id: UUID,
):
    _capture_file: Final[Path] = project_tests_dir / "mocks" / "create_study_job.json"

    def _default_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    respx_mock_from_capture(
        [mocked_webserver_service_api_base, mocked_directorv2_service_api_base],
        _capture_file,
        [_default_side_effect] * 7,
    )

    response = await client.post(
        f"{API_VTAG}/studies/{fake_study_id}/jobs",
        auth=auth,
        json={
            "values": {
                "input_file": {
                    "filename": "input.txt",
                    "id": "0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                },
            }
        },
    )
    assert response.status_code == 200


async def test_get_study_job_outputs(
    client: httpx.AsyncClient,
    fake_study_id: UUID,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api_base: MockRouter,
):
    job_id = "cfe9a77a-f71e-11ee-8fca-0242ac140008"

    capture = {
        "name": "GET /projects/cfe9a77a-f71e-11ee-8fca-0242ac140008/outputs",
        "description": "<Request('GET', 'http://webserver:8080/v0/projects/cfe9a77a-f71e-11ee-8fca-0242ac140008/outputs')>",
        "method": "GET",
        "host": "webserver",
        "path": {
            "path": "/v0/projects/{project_id}/outputs",
            "path_parameters": [
                {
                    "in": "path",
                    "name": "project_id",
                    "required": True,
                    "schema": {
                        "title": "Project Id",
                        "type": "str",
                        "pattern": None,
                        "format": "uuid",
                        "exclusiveMinimum": None,
                        "minimum": None,
                        "anyOf": None,
                        "allOf": None,
                        "oneOf": None,
                    },
                    "response_value": "projects",
                }
            ],
        },
        "query": None,
        "request_payload": None,
        "response_body": {"data": {}},
        "status_code": 200,
    }

    mocked_webserver_service_api_base.get(
        path=capture["path"]["path"].format(project_id=job_id)
    ).respond(
        status_code=capture["status_code"],
        json=capture["response_body"],
    )

    response = await client.post(
        f"{API_VTAG}/studies/{fake_study_id}/jobs/{job_id}/outputs",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    job_outputs = JobOutputs(**response.json())

    assert str(job_outputs.job_id) == job_id
    assert job_outputs.results == {}
