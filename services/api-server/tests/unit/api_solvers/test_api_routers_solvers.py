# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import httpx
from fastapi import status
from pydantic import TypeAdapter
from pytest_mock import MockType
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import OnePage
from simcore_service_api_server.models.schemas.solvers import Solver, SolverPort


async def test_list_all_solvers(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    response = await client.get(f"/{API_VTAG}/solvers", auth=auth)
    assert response.status_code == status.HTTP_200_OK


async def test_list_all_solvers_paginated(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    response = await client.get(f"/{API_VTAG}/solvers/page", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == response.json()["total"]


async def test_list_all_solvers_paginated_with_filters(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    # Test filter by solver_id
    response = await client.get(
        f"/{API_VTAG}/solvers/page?solver_id=simcore/services/comp/itis/*",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    solvers = response.json()["items"]
    assert all("simcore/services/comp/itis/" in solver["id"] for solver in solvers)

    # Test filter by version_display
    response = await client.get(
        f"/{API_VTAG}/solvers/page?version_display=*Xtreme*",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    solvers = response.json()["items"]
    assert all(
        solver["version_display"] and "Xtreme" in solver["version_display"]
        for solver in solvers
    )

    # Test combination of both filters
    response = await client.get(
        f"/{API_VTAG}/solvers/page?solver_id=simcore/services/comp/itis/*&version_display=*Xtreme*",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    solvers = response.json()["items"]
    assert all(
        "simcore/services/comp/itis/" in solver["id"]
        and solver["version_display"]
        and "Xtreme" in solver["version_display"]
        for solver in solvers
    )


async def test_list_all_solvers_releases(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    response = await client.get(f"/{API_VTAG}/solvers/releases", auth=auth)
    assert response.status_code == status.HTTP_200_OK


async def test_list_all_solvers_releases_paginated(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    solver_key = "simcore/services/comp/itis/sleeper"
    response = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/page", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == response.json()["total"]


async def test_list_solver_releases(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    solver_key = "simcore/services/comp/itis/sleeper"
    response = await client.get(f"/{API_VTAG}/solvers/{solver_key}/releases", auth=auth)
    assert response.status_code == status.HTTP_200_OK


async def test_get_solver_release(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    solver_key = "simcore/services/comp/itis/sleeper"
    solver_version = "2.2.1"
    response = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK

    solver = Solver.model_validate(response.json())
    assert solver.version_display == "2 Xtreme"


async def test_list_solver_ports(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    resp = await client.get(
        f"/{API_VTAG}/solvers/simcore/services/comp/itis/sleeper/releases/2.1.4/ports",
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK

    assert resp.json() == {
        "total": 2,
        "items": [
            {
                "key": "input_1",
                "kind": "input",
                "content_schema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            },
            {
                "key": "output_1",
                "kind": "output",
                "content_schema": {
                    "description": "Integer is generated in range [1-9]",
                    "title": "File containing one random integer",
                    "type": "string",
                },
            },
        ],
    }


async def test_list_solver_ports_again(
    mocked_catalog_rpc_api: dict[str, MockType],
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    solver_key = "simcore/services/comp/itis/sleeper"
    solver_version = "3.2.1"
    response = await client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/ports", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    assert TypeAdapter(OnePage[SolverPort]).validate_python(response.json())
