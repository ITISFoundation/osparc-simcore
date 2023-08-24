# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path
from typing import Any, TypedDict

import httpx
import pytest
from fastapi import status
from pydantic import parse_file_as, parse_obj_as
from respx import MockRouter
from simcore_service_api_server.models.schemas.errors import ErrorGet
from simcore_service_api_server.models.schemas.studies import Study, StudyID, StudyPort
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
    mocked_webserver_service_api: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "for_test_api_routes_studies.json"

    captures = {
        c.name: c
        for c in parse_file_as(
            list[HttpApiCallCaptureModel], project_tests_dir / "mocks" / mock_name
        )
    }

    for name in (
        "get_me",
        "list_projects",
        "get_project",
        "get_invalid_project",
        "get_project_ports",
        "get_invalid_project_ports",
    ):
        capture = captures[name]
        assert capture.host == "webserver"

        route = mocked_webserver_service_api.request(
            method=capture.method,
            path__regex=capture.path.removeprefix("/v0") + "$",
            name=capture.name,
        ).respond(
            status_code=capture.status_code,
            json=capture.response_body,
        )
        print(route)
    return MockedBackendApiDict(webserver=mocked_webserver_service_api, catalog=None)


@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4177"
)
async def test_studies_read_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_backend: MockRouter,
):
    study_id = StudyID("25531b1a-2565-11ee-ab43-02420a000031")

    # list_studies
    resp = await client.get("/v0/studies", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    studies = parse_obj_as(list[Study], resp.json()["items"])
    assert len(studies) == 1
    assert studies[0].uid == study_id

    # create_study doest NOT exist -> needs to be done via GUI
    resp = await client.post("/v0/studies", auth=auth)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # get_study
    resp = await client.get(f"/v0/studies/{study_id}", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    study = parse_obj_as(Study, resp.json())
    assert study.uid == study_id

    # get ports
    resp = await client.get(f"/v0/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    ports = parse_obj_as(list[StudyPort], resp.json()["items"])
    assert len(ports) == (resp.json()["total"])

    # get_study with non-existing uuid
    inexistent_study_id = StudyID("15531b1a-2565-11ee-ab43-02420a000031")
    resp = await client.get(f"/v0/studies/{inexistent_study_id}", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    error = parse_obj_as(ErrorGet, resp.json())
    assert f"{inexistent_study_id}" in error.errors[0]

    resp = await client.get(f"/v0/studies/{inexistent_study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    error = parse_obj_as(ErrorGet, resp.json())
    assert f"{inexistent_study_id}" in error.errors[0]


async def test_list_study_ports(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
    fake_study_ports: list[dict[str, Any]],
    study_id: StudyID,
):
    # Mocks /projects/{*}/metadata/ports

    mocked_webserver_service_api.get(
        path__regex=r"/projects/(?P<project_id>[\w-]+)/metadata/ports$",
        name="list_project_metadata_ports",
    ).respond(
        200,
        json={"data": fake_study_ports},
    )

    # list_study_ports
    resp = await client.get(f"/v0/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"items": fake_study_ports, "total": len(fake_study_ports)}


@pytest.mark.xfail(
    reason="Under dev: https://github.com/ITISFoundation/osparc-simcore/issues/4651"
)
async def test_clone_study(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    study_id: StudyID,
):
    resp = await client.post(f"/v0/studies/{study_id}:clone", auth=auth)
    assert resp.status_code == status.HTTP_201_CREATED
