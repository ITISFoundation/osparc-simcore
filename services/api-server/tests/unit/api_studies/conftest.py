# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Iterator
from copy import deepcopy
from typing import Any

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from pytest_simcore.helpers.faker_webserver import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.studies import StudyID


@pytest.fixture
def study_id(faker: Faker) -> StudyID:
    return faker.uuid4()


@pytest.fixture
def fake_study_ports() -> list[dict[str, Any]]:
    # NOTE: Reuses fakes used to test web-server API responses of /projects/{project_id}/metadata/ports
    # as reponses in this mock. SEE services/web/server/tests/unit/with_dbs/02/test_projects_ports_handlers.py
    return deepcopy(PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA)


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

    openapi = deepcopy(webserver_service_openapi_specs)
    oas_paths = openapi["paths"]

    # ENTRYPOINTS ---------
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # Mocks /health
        assert oas_paths["/v0/health"]
        assert (
            oas_paths["/v0/health"]["get"]["operationId"]
            == "healthcheck_liveness_probe"
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
        assert oas_paths["/v0/projects/{project_id}/metadata/ports"]
        assert "get" in oas_paths["/v0/projects/{project_id}/metadata/ports"]

        yield respx_mock
