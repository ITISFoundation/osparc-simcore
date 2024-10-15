# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import httpx
import pytest
import respx
from faker import Faker
from fastapi import status
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from respx import MockRouter
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobOutputs, JobStatus
from simcore_service_api_server.models.schemas.studies import JobLogsMap, Study, StudyID

_faker = Faker()


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

    study = Study.model_validate(resp.json())
    assert study.uid == study_id

    # Lists study jobs
    resp = await client.get("/v0/studies/{study_id}/jobs", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # Create Study Job
    resp = await client.post("/v0/studies/{study_id}/jobs", auth=auth)
    assert resp.status_code == status.HTTP_201_CREATED

    job = Job.model_validate(resp.json())
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
    create_respx_mock_from_capture: CreateRespxMockCallback,
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

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_service_api_base,
            mocked_directorv2_service_api_base,
        ],
        capture_path=capture_file,
        side_effects_callbacks=[_side_effect_no_project_id]
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
    _check_response(response, status.HTTP_202_ACCEPTED)

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


@pytest.mark.parametrize(
    "parent_node_id, parent_project_id",
    [(_faker.uuid4(), _faker.uuid4()), (None, None)],
)
@pytest.mark.parametrize("hidden", [True, False])
async def test_create_study_job(
    client: httpx.AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    fake_study_id: UUID,
    hidden: bool,
    parent_project_id: UUID | None,
    parent_node_id: UUID | None,
):
    _capture_file: Final[Path] = project_tests_dir / "mocks" / "create_study_job.json"

    def _default_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        if capture.method == "PATCH":
            _default_side_effect.patch_called = True
            request_content = json.loads(request.content.decode())
            assert isinstance(request_content, dict)
            name = request_content.get("name")
            assert name is not None
            project_id = path_params.get("project_id")
            assert project_id is not None
            assert project_id in name
        if capture.method == "POST":
            # test hidden boolean
            _default_side_effect.post_called = True
            query_dict = dict(
                elm.split("=") for elm in request.url.query.decode().split("&")
            )
            _hidden = query_dict.get("hidden")
            assert _hidden == ("true" if hidden else "false")

            # test parent project and node ids
            if parent_project_id is not None:
                assert f"{parent_project_id}" == dict(request.headers).get(
                    X_SIMCORE_PARENT_PROJECT_UUID.lower()
                )
            if parent_node_id is not None:
                assert f"{parent_node_id}" == dict(request.headers).get(
                    X_SIMCORE_PARENT_NODE_ID.lower()
                )
        return capture.response_body

    _default_side_effect.patch_called = False
    _default_side_effect.post_called = False

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_service_api_base,
            mocked_directorv2_service_api_base,
        ],
        capture_path=_capture_file,
        side_effects_callbacks=[_default_side_effect] * 5,
    )

    header_dict = {}
    if parent_project_id is not None:
        header_dict[X_SIMCORE_PARENT_PROJECT_UUID] = f"{parent_project_id}"
    if parent_node_id is not None:
        header_dict[X_SIMCORE_PARENT_NODE_ID] = f"{parent_node_id}"
    response = await client.post(
        f"{API_VTAG}/studies/{fake_study_id}/jobs",
        auth=auth,
        headers=header_dict,
        params={"hidden": f"{hidden}"},
        json={"values": {}},
    )
    assert response.status_code == 200
    assert _default_side_effect.patch_called
    assert _default_side_effect.post_called


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


async def test_get_job_logs(
    client: httpx.AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    _study_id = "7171cbf8-2fc9-11ef-95d3-0242ac140018"
    _job_id = "1a4145e2-2fca-11ef-a199-0242ac14002a"

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_directorv2_service_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "get_study_job_logs.json",
        side_effects_callbacks=[],
    )

    response = await client.get(
        f"{API_VTAG}/studies/{_study_id}/jobs/{_job_id}/outputs/log-links", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    _ = JobLogsMap.model_validate(response.json())


async def test_get_study_outputs(
    client: httpx.AsyncClient,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    mocked_directorv2_service_api_base,
    mocked_webserver_service_api_base,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):

    _study_id = "e9f34992-436c-11ef-a15d-0242ac14000c"

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_directorv2_service_api_base,
            mocked_webserver_service_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "get_job_outputs.json",
        side_effects_callbacks=[],
    )

    response = await client.post(
        f"/{API_VTAG}/studies/{_study_id}/jobs",
        auth=auth,
        json={
            "values": {
                "inputfile": {
                    "filename": "inputfile",
                    "id": "c1dcde67-6434-31c3-95ee-bf5fe1e9422d",
                }
            }
        },
    )
    assert response.status_code == status.HTTP_200_OK
    _job = Job.model_validate(response.json())
    _job_id = _job.id

    response = await client.post(
        f"/{API_VTAG}/studies/{_study_id}/jobs/{_job_id}:start", auth=auth
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    _ = JobStatus.model_validate(response.json())

    response = await client.post(
        f"/{API_VTAG}/studies/{_study_id}/jobs/{_job_id}/outputs", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    _ = JobOutputs.model_validate(response.json())
