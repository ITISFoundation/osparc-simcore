# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockType
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server.models.schemas.solvers import Solver


async def test_get_solver(
    mocked_rpc_client: MockType,
    solver_service: SolverService,
    product_name: ProductName,
    user_id: UserID,
):
    solver = await solver_service.get_solver(
        user_id=user_id,
        solver_key="simcore/services/comp/solver-1",
        solver_version="1.0.0",
        product_name=product_name,
    )

    assert isinstance(solver, Solver)
    assert solver.id == "simcore/services/comp/solver-1"

    assert mocked_rpc_client.request.called
    assert mocked_rpc_client.request.call_args.args == ("catalog", "get_service")


async def test_list_jobs(
    mocked_rpc_client: MockType,
    solver_service: SolverService,
):
    # Test default parameters
    jobs, page_meta = await solver_service.list_jobs()

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
