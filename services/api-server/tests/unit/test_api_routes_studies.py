# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.faker_webserver import (
    PROJECTS_METADATA_PORTS_RESPOSE_BODY_DATA,
)
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.studies import StudyID


@pytest.fixture(scope="session")
def webserver_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:

    openapi_path = (
        osparc_simcore_services_dir
        / "web/server/src/simcore_service_webserver/api/v0/openapi.yaml"
    )
    openapi_specs = json.loads(openapi_path.read_text())
    return openapi_specs


@pytest.fixture
def study_id(faker: Faker) -> StudyID:
    return faker.uuid4()


@pytest.fixture
def fake_study_ports() -> list[dict[str, Any]]:
    # NOTE: Reuses fakes used to test web-server API responses of /projects/{project_id}/metadata/ports
    # as reponses in this mock. SEE services/web/server/tests/unit/with_dbs/02/test_projects_ports_handlers.py
    return deepcopy(PROJECTS_METADATA_PORTS_RESPOSE_BODY_DATA)


@pytest.fixture
def mocked_webserver_service_api(
    app: FastAPI,
    webserver_service_openapi_specs: dict[str, Any],
    fake_study_ports: list[dict[str, Any]],
    faker: Faker,
) -> Iterator[MockRouter]:
    """
    Mocks web/server http API
    """
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    # TODO: add more examples in openapi!
    openapi = deepcopy(webserver_service_openapi_specs)
    oas_paths = openapi["paths"]

    # ENTRYPOINTS ---------
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        # Mocks /health
        assert oas_paths["/health"]
        respx_mock.get("/v0/health").respond(
            200,
            json={
                "data": {
                    "name": "simcore-director-service",
                    "status": "SERVICE_RUNNING",
                    "api_version": "0.1.0-dev+NJuzzD9S",
                    "version": "0.1.0-dev+N127Mfv9H",
                }
            },
        )

        # Mocks /projects/{*}/metadata/ports
        assert oas_paths["/projects/{project_id}/metadata/ports"]
        assert "get" in oas_paths["/projects/{project_id}/metadata/ports"].keys()
        respx_mock.get(
            path__regex=r"/v0/projects/(?P<project_id>[\w-]+)/metadata/ports",
            name="list_project_metadata_ports",
        ).respond(
            200,
            json={"data": fake_study_ports},
        )

        yield respx_mock


async def test_mocked_webserver_service_api(
    client: httpx.AsyncClient,
    mocked_webserver_service_api: MockRouter,
    fake_study_ports: list[dict[str, Any]],
):
    # Sometimes is difficult to adjust respx.Mock
    resp = await client.get(f"/v0/study/{study_id}/ports")

    assert mocked_webserver_service_api.assert_all_called()

    assert resp.status_code == status.HTTP_200_OK

    payload = resp.json()
    assert payload.get("error") is None
    assert payload.get("data") == fake_study_ports


async def test_study_io_ports_workflow(
    client: httpx.AsyncClient,
    mocked_webserver_service_api: MockRouter,
    faker: Faker,
    fake_study_ports: list[dict[str, Any]],
    study_id: StudyID,
):
    study_id = faker.uuid4()

    # list_study_ports
    resp = await client.get(f"/v0/study/{study_id}/ports")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == fake_study_ports
