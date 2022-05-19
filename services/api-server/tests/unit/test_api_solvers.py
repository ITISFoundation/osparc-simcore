# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Iterator

import _catalog_fakes

import urllib
import urllib.parse

import pytest
import respx
import simcore_service_api_server.api.routes.solvers
from faker import Faker
from fastapi import FastAPI
from httpx import AsyncClient
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from requests.auth import HTTPBasicAuth
from respx.router import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import AppSettings
from simcore_service_api_server.models.schemas.solvers import Solver
from starlette import status


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


# -----------------------------------------------------
@pytest.fixture
def mocked_directorv2_service_api(app: FastAPI, faker: Faker):
    assert app.state
    with respx.mock(
        base_url=app.state.settings.API_SERVER_DIRECTOR_V2.base_url,
        assert_all_called=False,
        assert_all_mocked=False,
    ) as respx_mock:
        respx_mock.get(
            "/v2/computations/{project_id}/tasks/-/logs",
            name="director_v2.get_computation_logs",
        ).respond(
            status.HTTP_200_OK,
            json={"iSolve": faker.url()},
        )

        yield respx_mock


def test_solver_logs(
    sync_client: TestClient, faker: Faker, mocked_directorv2_service_api: MockRouter
):
    resp = sync_client.get("/v0/meta")
    assert resp.status_code == 200

    solver_key = urllib.parse.quote_plus("simcore/services/comp/itis/isolve")
    version = "1.2.3"
    job_id = faker.uuid4()

    resp = sync_client.get(
        f"/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}/outputs/logs",
        auth=HTTPBasicAuth("user", "pass"),
    )

    assert mocked_directorv2_service_api["director_v2.get_computation_logs"].called
    assert resp.status_code == 200
