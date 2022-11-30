# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest
import respx
import yaml
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
    openapi_specs = yaml.safe_load(openapi_path.read_text())
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
        assert (
            oas_paths["/health"]["get"]["operationId"] == "healthcheck_liveness_probe"
        )
        # 'http://webserver:8080/v0/health'
        respx_mock.get("/health", name="healthcheck_liveness_probe").respond(
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
            path__regex=r"/projects/(?P<project_id>[\w-]+)/metadata/ports$",
            name="list_project_metadata_ports",
        ).respond(
            200,
            json={"data": fake_study_ports},
        )

        yield respx_mock


def test_mocked_webserver_service_api(
    app: FastAPI,
    mocked_webserver_service_api: MockRouter,
    study_id: StudyID,
    fake_study_ports: list[dict[str, Any]],
):
    #
    # This test intends to help building the urls in mocked_webserver_service_api
    # At some point, it can be skipped and reenabled only for development
    #
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER
    webserver_api_baseurl = settings.API_SERVER_WEBSERVER.base_url

    resp = httpx.get(f"{webserver_api_baseurl}/health")
    assert resp.status_code == status.HTTP_200_OK

    # Sometimes is difficult to adjust respx.Mock
    resp = httpx.get(f"{webserver_api_baseurl}/projects/{study_id}/metadata/ports")
    assert resp.status_code == status.HTTP_200_OK

    payload = resp.json()
    assert payload.get("error") is None
    assert payload.get("data") == fake_study_ports

    mocked_webserver_service_api.assert_all_called()


async def test_list_study_ports(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
    fake_study_ports: list[dict[str, Any]],
    study_id: StudyID,
):
    # list_study_ports
    resp = await client.get(f"/v0/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == fake_study_ports
