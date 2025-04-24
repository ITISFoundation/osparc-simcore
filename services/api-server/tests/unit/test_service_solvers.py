# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_rpc.catalog import CatalogService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


@pytest.fixture
def solver_service(
    mocker: MockerFixture,
    mocked_catalog_rpc_api: dict[str, MockType],
    mocked_webserver_rpc_api: dict[str, MockType],
) -> SolverService:
    return SolverService(
        catalog_service=CatalogService(client=mocker.MagicMock()),
        webserver_client=WbApiRpcClient(_client=mocker.MagicMock()),
    )


async def test_get_solver(
    solver_service: SolverService,
    mocked_catalog_rpc_api: dict[str, MockType],
    product_name: ProductName,
    user_id: UserID,
):
    solver = await solver_service.get_solver(
        user_id=user_id,
        name="simcore/services/comp/solver-1",
        version="1.0.0",
        product_name=product_name,
    )

    assert isinstance(solver, Solver)
    mocked_catalog_rpc_api["get_service"].assert_called_once()


async def test_list_jobs(
    solver_service: SolverService,
    mocked_webserver_rpc_api: dict[str, MockType],
    product_name: ProductName,
    user_id: UserID,
):
    # Test default parameters
    jobs, page_meta = await solver_service.list_jobs(
        user_id=user_id,
        product_name=product_name,
    )
    assert isinstance(jobs, list)
    mocked_webserver_rpc_api["list_projects_marked_as_jobs"].assert_called_once()
    assert page_meta.total >= 0
    assert page_meta.limit == 49
    assert page_meta.offset == 0
    assert page_meta.count > 0
