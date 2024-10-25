# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

import httpx
import pytest
from faker import Faker
from fastapi import status
from pydantic import TypeAdapter
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from respx import MockRouter
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.errors import ErrorGet
from simcore_service_api_server.models.schemas.studies import Study, StudyID, StudyPort

_faker = Faker()


class MockedBackendApiDict(TypedDict):
    catalog: MockRouter | None
    webserver: MockRouter | None


@pytest.fixture
def mocked_backend(
    mocked_webserver_service_api_base: MockRouter,
    project_tests_dir: Path,
) -> MockedBackendApiDict:
    mock_name = "for_test_api_routes_studies.json"

    captures = {
        c.name: c
        for c in TypeAdapter(list[HttpApiCallCaptureModel]).validate_json(
            Path(project_tests_dir / "mocks" / mock_name).read_text()
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

        route = mocked_webserver_service_api_base.request(
            method=capture.method,
            path__regex=capture.path.removeprefix("/v0") + "$",
            name=capture.name,
        ).respond(
            status_code=capture.status_code,
            json=capture.response_body,
        )
        print(route)
    return MockedBackendApiDict(
        webserver=mocked_webserver_service_api_base, catalog=None
    )


@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4177"
)
async def test_studies_read_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_backend: MockedBackendApiDict,
):
    study_id = StudyID("25531b1a-2565-11ee-ab43-02420a000031")

    # list_studies
    resp = await client.get(f"/{API_VTAG}/studies", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    studies = TypeAdapter(list[Study]).validate_python(resp.json()["items"])
    assert len(studies) == 1
    assert studies[0].uid == study_id

    # create_study doest NOT exist -> needs to be done via GUI
    resp = await client.post(f"/{API_VTAG}/studies", auth=auth)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # get_study
    resp = await client.get(f"/{API_VTAG}/studies/{study_id}", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    study = TypeAdapter(Study).validate_python(resp.json())
    assert study.uid == study_id

    # get ports
    resp = await client.get(f"/{API_VTAG}/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    ports = TypeAdapter(list[StudyPort]).validate_python(resp.json()["items"])
    assert len(ports) == (resp.json()["total"])

    # get_study with non-existing uuid
    inexistent_study_id = StudyID("15531b1a-2565-11ee-ab43-02420a000031")
    resp = await client.get(f"/{API_VTAG}/studies/{inexistent_study_id}", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    error = TypeAdapter(ErrorGet).validate_python(resp.json())
    assert f"{inexistent_study_id}" in error.errors[0]

    resp = await client.get(
        f"/{API_VTAG}/studies/{inexistent_study_id}/ports", auth=auth
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    error = TypeAdapter(ErrorGet).validate_python(resp.json())
    assert f"{inexistent_study_id}" in error.errors[0]


async def test_list_study_ports(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api_base: MockRouter,
    fake_study_ports: list[dict[str, Any]],
    study_id: StudyID,
):
    # Mocks /projects/{*}/metadata/ports

    mocked_webserver_service_api_base.get(
        path__regex=r"/projects/(?P<project_id>[\w-]+)/metadata/ports$",
        name="list_project_metadata_ports",
    ).respond(
        200,
        json={"data": fake_study_ports},
    )

    # list_study_ports
    resp = await client.get(f"/{API_VTAG}/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"items": fake_study_ports, "total": len(fake_study_ports)}


@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4651"
)
@pytest.mark.parametrize(
    "parent_node_id, parent_project_id",
    [(_faker.uuid4(), _faker.uuid4()), (None, None)],
)
async def test_clone_study(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    study_id: StudyID,
    mocked_webserver_service_api_base: MockRouter,
    patch_webserver_long_running_project_tasks: Callable[[MockRouter], MockRouter],
    parent_project_id: UUID | None,
    parent_node_id: UUID | None,
):
    # Mocks /projects
    patch_webserver_long_running_project_tasks(mocked_webserver_service_api_base)

    callback = mocked_webserver_service_api_base["create_projects"].side_effect
    assert callback is not None

    def clone_project_side_effect(request: httpx.Request):
        if parent_project_id is not None:
            _parent_project_id = dict(request.headers).get(
                X_SIMCORE_PARENT_PROJECT_UUID.lower()
            )
            assert _parent_project_id == f"{parent_project_id}"
        if parent_node_id is not None:
            _parent_node_id = dict(request.headers).get(
                X_SIMCORE_PARENT_NODE_ID.lower()
            )
            assert _parent_node_id == f"{parent_node_id}"
        return callback(request)

    mocked_webserver_service_api_base[
        "create_projects"
    ].side_effect = clone_project_side_effect

    _headers = {}
    if parent_project_id is not None:
        _headers[X_SIMCORE_PARENT_PROJECT_UUID] = f"{parent_project_id}"
    if parent_node_id is not None:
        _headers[X_SIMCORE_PARENT_NODE_ID] = f"{parent_node_id}"
    resp = await client.post(
        f"/{API_VTAG}/studies/{study_id}:clone", headers=_headers, auth=auth
    )

    assert mocked_webserver_service_api_base["create_projects"].called

    assert resp.status_code == status.HTTP_201_CREATED


async def test_clone_study_not_found(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    faker: Faker,
    mocked_webserver_service_api_base: MockRouter,
    patch_webserver_long_running_project_tasks: Callable[[MockRouter], MockRouter],
):
    # Mocks /projects
    mocked_webserver_service_api_base.post(
        path__regex=r"/projects",
        name="project_clone",
    ).respond(
        status.HTTP_404_NOT_FOUND,
        json={"message": "you should not read this message from the WEBSERVER_MARK"},
    )

    # tests unknown study
    unknown_study_id = faker.uuid4()
    resp = await client.post(f"/{API_VTAG}/studies/{unknown_study_id}:clone", auth=auth)

    assert resp.status_code == status.HTTP_404_NOT_FOUND

    errors: list[str] = resp.json()["errors"]
    assert any("WEBSERVER_MARK" not in error_msg for error_msg in errors)
