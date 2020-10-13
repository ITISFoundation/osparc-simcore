# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
import respx
from starlette.testclient import TestClient
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import AppSettings
from simcore_service_api_server.models.schemas.solvers import SolverOverview

from fastapi import FastAPI
from starlette import status

pytestmark = pytest.mark.asyncio


@pytest.fixture
def app(project_env_devel_environment, monkeypatch) -> FastAPI:
    # overrides conftest.py: app
    # uses packages/pytest-simcore/src/pytest_simcore/environment_configs.py: env_devel_config

    # Adds Dockerfile environs
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # settings from environs
    settings = AppSettings.create_from_env()
    settings.postgres.enabled = False
    settings.webserver.enabled = False
    settings.catalog.enabled = True

    mini_app = init_app(settings)
    return mini_app


@pytest.fixture
def mocked_catalog_service_api(app: FastAPI):
    def create_service(**overrides):
        # TODO: fake from Catalog schemas classes
        obj = {
            "name": "Fast Counter",
            "key": "simcore/services/comp/itis/sleeper",
            "version": "1.0.0",
            "integration-version": "1.0.0",
            "type": "computational",
            "authors": [
                {
                    "name": "Jim Knopf",
                    "email": ["sun@sense.eight", "deleen@minbar.bab"],
                    "affiliation": ["Sense8", "Babylon 5"],
                }
            ],
            "contact": "lab@net.flix",
            "inputs": {},
            "outputs": {},
            "owner": "user@example.com",
        }
        obj.update(**overrides)
        return obj

    with respx.mock(
        base_url=app.state.settings.director.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            "/v0/services",
            content={
                [
                    create_service(version="0.0.1"),
                    create_service(version="1.0.1"),
                    create_service(type="dynamic"),
                ]
            },
            alias="list_services",
        )

        yield respx_mock


def test_list_solvers(sync_client: TestClient, mocked_catalog_service_api):

    resp = sync_client.get("/v0/solvers")

    assert resp.status_code == status.HTTP_200_OK

    # validates response
    available_solvers = [SolverOverview.parse_obj(**s) for s in resp.json()]
