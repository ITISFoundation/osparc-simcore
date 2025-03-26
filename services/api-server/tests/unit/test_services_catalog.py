# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.catalog_rpc_server import CatalogRpcSideEffects
from simcore_service_api_server.models.schemas.solvers import Solver, SolverPort
from simcore_service_api_server.services_rpc.catalog import CatalogService, catalog_rpc


@pytest.fixture
def product_name() -> ProductName:
    return "osparc"


@pytest.fixture
def mocked_rpc_catalog_service_api(mocker: MockerFixture) -> dict[str, MockType]:

    side_effects = CatalogRpcSideEffects()

    return {
        "list_services_paginated": mocker.patch.object(
            catalog_rpc,
            "list_services_paginated",
            autospec=True,
            side_effect=side_effects.list_services_paginated,
        ),
        "get_service": mocker.patch.object(
            catalog_rpc,
            "get_service",
            autospec=True,
            side_effect=side_effects.get_service,
        ),
        "update_service": mocker.patch.object(
            catalog_rpc,
            "update_service",
            autospec=True,
            side_effect=side_effects.update_service,
        ),
    }


async def test_catalog_service_read_solvers(
    product_name: ProductName,
    user_id: UserID,
    mocker: MockerFixture,
    mocked_rpc_catalog_service_api: dict[str, MockType],
):

    catalog_service = CatalogService(_client=mocker.MagicMock())
    catalog_service.set_to_app_state(app=FastAPI())

    # Step 1: List latest releases in a page
    solver_releases_page, meta = await catalog_service.list_latest_releases(
        product_name=product_name, user_id=user_id
    )
    assert solver_releases_page, "Releases page should not be empty"
    assert meta.offset == 0

    # Step 2: Select one release and list solver releases
    selected_release = solver_releases_page[0]
    solver_releases, meta = await catalog_service.list_solver_releases(
        product_name=product_name,
        user_id=user_id,
        solver_id=selected_release.id,
    )
    assert solver_releases, "Solver releases should not be empty"
    assert meta.offset == 0

    # Step 3: Take the latest solver release and get solver details
    latest_solver_release = solver_releases[0]
    solver_details: Solver | None = await catalog_service.get_solver(
        product_name=product_name,
        user_id=user_id,
        solver_id=latest_solver_release.id,
        solver_version=latest_solver_release.version,
    )
    assert solver_details, "Solver details should not be empty"

    # Step 4: Get solver ports
    solver_ports: list[SolverPort] = await catalog_service.get_solver_ports(
        product_name=product_name,
        user_id=user_id,
        solver_id=latest_solver_release.id,
        solver_version=latest_solver_release.version,
    )
    assert solver_ports, "Solver ports should not be empty"
