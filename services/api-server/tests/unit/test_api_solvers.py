# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
import respx
from fastapi import FastAPI
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import AppSettings
from simcore_service_api_server.models.schemas.solvers import Solver
from starlette import status
from starlette.testclient import TestClient


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

import catalog_fakes
@pytest.fixture
def mocked_catalog_service_api(app: FastAPI):
    with respx.mock(
        base_url=app.state.settings.catalog.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            "/v0/services?user_id=1&details=false",
            status_code=200,
            content=[
                catalog_fakes.create_service_out(version="0.0.1"),
                catalog_fakes.create_service_out(version="1.0.1"),
                catalog_fakes.create_service_out(type="dynamic"),
            ],
            alias="list_services",
            content_type="application/json",
        )

        yield respx_mock


def test_list_solvers(sync_client: TestClient, mocked_catalog_service_api):
    cli = sync_client

    # list solvers latest releases
    resp = cli.get("/v0/solvers")
    assert resp.status_code == status.HTTP_200_OK
    for item in resp.json():
        solver = Solver(**item)
        print(solver.json(indent=1))

        # use link to get the same solver
        assert solver.solver_url.host == "api.testserver.io"
        resp = cli.get(solver.solver_url.path)
        assert solver == Solver(**resp.json())

        # get latest by name
        resp = cli.get(f"{solver.name}/latest")
        latest_solver = Solver(**resp.json())
        assert latest_solver == solver
