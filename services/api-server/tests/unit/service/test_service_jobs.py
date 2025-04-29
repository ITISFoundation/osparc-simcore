# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from simcore_service_api_server.models.schemas.solvers import Solver


async def test_list_jobs_by_resource_prefix(
    job_service: JobService,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    # Test with default pagination parameters
    jobs, page_meta = await job_service.list_jobs_by_resource_prefix(
        job_parent_resource_name_prefix="solvers/some-solver"
    )

    assert isinstance(jobs, list)
    mocked_webserver_rpc_api["list_projects_marked_as_jobs"].assert_called_once()

    # Check pagination info
    assert page_meta.total >= 0
    assert page_meta.limit > 0
    assert page_meta.offset == 0


async def test_create_job(
    job_service: JobService,
    mocked_webserver_rest_api_base: dict[str, MockType],
    mocked_webserver_rpc_api: dict[str, MockType],
    product_name: ProductName,
    user_id: UserID,
):
    # Create mock solver and inputs
    solver = Solver(
        id="simcore/services/comp/test-solver",
        version="1.0.0",
        title="Test Solver",
        maintainer="test@example.com",
        description="Test solver for testing",
    )

    inputs = JobInputs(items={})

    # Mock URL generator
    def mock_url_for(*args, **kwargs):
        return "https://example.com/api/v1/jobs/test-job"

    # Test job creation
    job, project = await job_service.create_job(
        solver_or_program=solver,
        inputs=inputs,
        parent_project_uuid=None,
        parent_node_id=None,
        url_for=mock_url_for,
        hidden=False,
        project_name="Test Job Project",
        description="Test description",
    )

    # Verify job and project creation
    assert isinstance(job, Job)
    assert job.id == project.uuid
    assert "test-solver" in job.name

    # Verify API calls
    mocked_webserver_rest_api_base["create_project"].assert_called_once()
    mocked_webserver_rpc_api["mark_project_as_job"].assert_called_once()
