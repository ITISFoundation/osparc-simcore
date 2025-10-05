# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from models_library.api_schemas_catalog.services import LatestServiceGet, ServiceGetV2
from models_library.products import ProductName
from models_library.services_history import ServiceRelease
from models_library.users import UserID
from pydantic import HttpUrl
from pytest_mock import MockType
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_rpc.catalog import CatalogService


def _to_solver_schema(
    service: LatestServiceGet | ServiceGetV2, href_self: HttpUrl | None = None
) -> Solver:
    # NOTE: this is an adapter around models on CatalogService interface
    return Solver(
        id=service.key,
        version=service.version,
        title=service.name,
        maintainer=service.owner or service.contact or "UNKNOWN",
        url=href_self,
        description=service.description,
    )


async def test_catalog_service_read_solvers(
    product_name: ProductName,
    user_id: UserID,
    mocked_rabbit_rpc_client: MockType,
    catalog_service: CatalogService,
):
    # Step 1: List latest releases in a page
    latest_releases, meta = await catalog_service.list_latest_releases()
    solver_releases_page = [_to_solver_schema(srv) for srv in latest_releases]

    assert solver_releases_page, "Releases page should not be empty"
    assert meta.offset == 0

    # Step 2: Select one release and list solver releases
    selected_solver = solver_releases_page[0]
    releases, meta = await catalog_service.list_release_history_latest_first(
        filter_by_service_key=selected_solver.id,
    )
    assert releases, "Solver releases should not be empty"
    assert meta.offset == 0

    # Step 3: Take the latest solver release and get solver details
    oldest_release: ServiceRelease = releases[-1]

    service: ServiceGetV2 = await catalog_service.get(
        name=selected_solver.id,
        version=oldest_release.version,
    )
    solver = _to_solver_schema(service)
    assert solver.id == selected_solver.id
    assert solver.version == oldest_release.version

    # Step 4: Get service ports for the solver
    ports = await catalog_service.get_service_ports(
        name=selected_solver.id,
        version=oldest_release.version,
    )

    # Verify ports are returned and contain both inputs and outputs
    assert ports, "Service ports should not be empty"
    assert any(port.kind == "input" for port in ports), "Should contain input ports"
    assert any(port.kind == "output" for port in ports), "Should contain output ports"

    # checks calls to rpc
    assert mocked_rabbit_rpc_client.request.call_count == 4
    assert mocked_rabbit_rpc_client.request.call_args_list[0].args == (
        "catalog",
        "list_services_paginated",
    )
    assert mocked_rabbit_rpc_client.request.call_args_list[1].args == (
        "catalog",
        "list_my_service_history_latest_first",
    )
    assert mocked_rabbit_rpc_client.request.call_args_list[2].args == (
        "catalog",
        "get_service",
    )
    assert mocked_rabbit_rpc_client.request.call_args_list[3].args == (
        "catalog",
        "get_service_ports",
    )
