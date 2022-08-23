# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import httpx
import pytest
import simcore_service_api_server.api.routes.solvers
from respx import MockRouter
from simcore_service_api_server.models.schemas.solvers import Solver
from starlette import status


@pytest.mark.skip(reason="Still under development. Currently using fake implementation")
async def test_list_solvers(
    client: httpx.AsyncClient,
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
