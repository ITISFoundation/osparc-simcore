# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Iterator

import _catalog_fakes
import pytest
import respx
import simcore_service_api_server.api.routes.solvers
from fastapi import FastAPI
from httpx import AsyncClient
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from respx import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.solvers import Solver
from starlette import status


@pytest.fixture
def app(
    patched_project_env_devel_vars: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> FastAPI:
    # overrides conftest.py: app

    # Adds Dockerfile environs
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # settings from environs
    settings = ApplicationSettings.create_from_envs()
    settings.API_SERVER_POSTGRES = None
    settings.API_SERVER_WEBSERVER = None
    settings.API_SERVER_CATALOG = None

    mini_app = init_app(settings)
    return mini_app


@pytest.fixture
def mocked_catalog_service_api(app: FastAPI) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get(
            "/services?user_id=1&details=false", name="list_services"
        ).respond(
            200,
            json=[
                # one solver
                _catalog_fakes.create_service_out(
                    key="simcore/services/comp/Foo", name="Foo"
                ),
                # two version of the same solver
                _catalog_fakes.create_service_out(version="0.0.1"),
                _catalog_fakes.create_service_out(version="1.0.1"),
                # not a solver
                _catalog_fakes.create_service_out(type="dynamic"),
            ],
        )

        yield respx_mock


@pytest.mark.skip(reason="Still under development. Currently using fake implementation")
async def test_list_solvers(
    client: AsyncClient,
    mocked_catalog_service_api: MockRouter,
    mocker,
):
    warn = mocker.patch.object(
        simcore_service_api_server.api.routes.solvers.logger, "warning"
    )

    # list solvers latest releases
    resp = await client.get("/v0/solvers")
    assert resp.status_code == status.HTTP_200_OK

    # No warnings for ValidationError with the fixture
    assert (
        not warn.called
    ), f"No warnings expected in this fixture, got {str(warn.call_args)}"

    data = resp.json()
    assert len(data) == 2

    for item in data:
        solver = Solver(**item)
        print(solver.json(indent=1, exclude_unset=True))

        # use link to get the same solver
        assert solver.url.host == "api.testserver.io"  # cli.base_url

        # get_solver_latest_version_by_name
        resp0 = await client.get(solver.url.path)
        assert resp0.status_code == status.HTTP_501_NOT_IMPLEMENTED
        # assert f"GET {solver.name}:{solver.version}"  in resp0.json()["errors"][0]
        assert f"GET solver {solver.id}" in resp0.json()["errors"][0]
        # assert Solver(**resp0.json()) == solver

        # get_solver
        resp1 = await client.get(f"/v0/solvers/{solver.id}")
        assert resp1.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert f"GET solver {solver.id}" in resp1.json()["errors"][0]
        # assert Solver(**resp1.json()) == solver

        # get_solver_latest_version_by_name
        resp2 = await client.get(f"/v0/solvers/{solver.id}/latest")

        assert resp2.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert f"GET latest {solver.id}" in resp2.json()["errors"][0]

        # assert Solver(**resp2.json()) == Solver(**resp3.json())
