# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rpc.webserver.projects import ProjectJobRpcGet
from models_library.users import UserID
from pytest_mock import MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server.exceptions.custom_errors import (
    ServiceConfigurationError,
)
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_rpc.catalog import CatalogService
from simcore_service_api_server.services_rpc.wb_api_server import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)


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


async def test_job_service_get_job_success(
    mocked_rpc_client: MockType,
    job_service: JobService,
):
    job_parent_resource_name = "solver-resource"
    job_id = ProjectID("123e4567-e89b-12d3-a456-426614174000")

    # Act
    result = await job_service.get_job(job_parent_resource_name, job_id)

    # Assert
    assert isinstance(result, ProjectJobRpcGet)
    assert result.job_parent_resource_name.startswith(job_parent_resource_name)
    assert mocked_rpc_client.request.called
    assert mocked_rpc_client.request.call_args.args == (
        "webserver",
        "get_project_marked_as_job",
    )
    assert (
        mocked_rpc_client.request.call_args.kwargs["job_parent_resource_name"]
        == job_parent_resource_name
    )
    assert mocked_rpc_client.request.call_args.kwargs["project_uuid"] == job_id


@pytest.mark.parametrize(
    "exception_type",
    [ProjectForbiddenRpcError, ProjectNotFoundRpcError],
)
async def test_job_service_get_job_exceptions(
    mocker, job_service: JobService, exception_type
):
    job_parent_resource_name = "solver-resource"
    job_id = ProjectID("123e4567-e89b-12d3-a456-426614174000")
    mocker.patch.object(
        job_service._web_rpc_client,
        "get_project_marked_as_job",
        side_effect=exception_type("error"),
    )

    with pytest.raises(exception_type):
        await job_service.get_job(job_parent_resource_name, job_id)
        await job_service.get_job(job_parent_resource_name, job_id)
