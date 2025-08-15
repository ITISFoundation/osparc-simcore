# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server.exceptions.custom_errors import (
    ServiceConfigurationError,
)
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_rpc.catalog import CatalogService


async def test_get_solver(
    mocked_rpc_client: MockType,
    solver_service: SolverService,
    product_name: ProductName,
    user_id: UserID,
):
    solver = await solver_service.get_solver(
        solver_key="simcore/services/comp/solver-1",
        solver_version="1.0.0",
    )

    assert isinstance(solver, Solver)
    assert solver.id == "simcore/services/comp/solver-1"

    assert mocked_rpc_client.request.called
    assert mocked_rpc_client.request.call_args.args == ("catalog", "get_service")


async def test_list_jobs(
    mocked_rpc_client: MockType,
    job_service: JobService,
):
    # Test default parameters
    jobs, page_meta = await job_service.list_solver_jobs()

    assert jobs
    assert len(jobs) == page_meta.count

    assert mocked_rpc_client.request.call_args.args == (
        "webserver",
        "list_projects_marked_as_jobs",
    )

    assert page_meta.total >= 0
    assert page_meta.limit >= page_meta.count
    assert page_meta.offset == 0
    assert page_meta.count > 0


async def test_solver_service_init_raises_configuration_error(
    mocked_rpc_client: MockType,
    job_service: JobService,
    catalog_service: CatalogService,
    user_id: UserID,
):
    # Create a product name that is inconsistent with the user_id
    invalid_product_name = ProductName("invalid_product")

    with pytest.raises(ServiceConfigurationError, match="SolverService"):
        SolverService(
            catalog_service=catalog_service,
            job_service=job_service,
            user_id=user_id,
            product_name=invalid_product_name,
        )
    # Verify the RPC call was made to check consistency
    assert not mocked_rpc_client.request.called
