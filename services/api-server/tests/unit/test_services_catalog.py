# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from simcore_service_api_server.models.schemas.solvers import Solver, SolverPort
from simcore_service_api_server.services_rpc import catalog as catalog_service


@pytest.fixture
def product_name() -> ProductName:
    return "osparc"


async def test_catalog_service_read_solvers(product_name: ProductName, user_id: UserID):
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
