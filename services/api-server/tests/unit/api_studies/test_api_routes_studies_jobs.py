# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import httpx
import pytest
from fastapi import status
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server.models.schemas.jobs import Job
from simcore_service_api_server.models.schemas.studies import Study, StudyID


@pytest.mark.xfail(reason="Still not implemented")
@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4177"
)
async def test_studies_jobs_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api_base: MockRouter,
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
