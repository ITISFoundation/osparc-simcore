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
    mocked_rpc_catalog_service_api: dict[str, MockType],
) -> SolverService:
    return SolverService(
        catalog_service=CatalogService(client=mocker.MagicMock()),
        webserver_client=WbApiRpcClient(_client=mocker.MagicMock()),
    )


async def test_get_solver(
    solver_service: SolverService,
    mocked_rpc_catalog_service_api: dict[str, MockType],
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
    mocked_rpc_catalog_service_api["get_service"].assert_called_once()
