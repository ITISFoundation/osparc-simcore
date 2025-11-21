# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from faker import Faker
from pytest_mock import MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from simcore_service_api_server.models.schemas.solvers import Solver

_faker = Faker()


async def test_list_jobs_by_resource_prefix(
    mocked_rabbit_rpc_client: MockType,
    job_service: JobService,
):
    # Test with default pagination parameters
    jobs, page_meta = await job_service._list_jobs(
        job_parent_resource_name="solvers/some-solver"
    )

    assert isinstance(jobs, list)

    assert len(jobs) == page_meta.count
    assert mocked_rabbit_rpc_client.request.call_args.args == (
        "webserver",
        "list_projects_marked_as_jobs",
    )

    # Check pagination info
    assert page_meta.total >= 0
    assert page_meta.limit > 0
    assert page_meta.offset == 0


async def test_create_job(
    mocked_rabbit_rpc_client: MockType,
    job_service: JobService,
):
    # Create mock solver and inputs
    solver = Solver(
        id="simcore/services/comp/test-solver",
        version="1.0.0",
        title="Test Solver",
        maintainer="test@example.com",
        description="Test solver for testing",
        url=None,
    )

    inputs = JobInputs(values={})

    # Mock URL generator
    def mock_url_for(*args, **kwargs):
        return "https://example.com/api/v1/jobs/test-job"

    job_rest_interface_links = JobLinks(
        url_template=_faker.url() + "/{job_id}",
        runner_url_template=_faker.url(),
        outputs_url_template=_faker.url() + "/{job_id}",
    )

    # Test job creation
    job, project = await job_service.create_project_marked_as_job(
        solver_or_program=solver,
        inputs=inputs,
        parent_project_uuid=None,
        parent_node_id=None,
        job_links=job_rest_interface_links,
        hidden=False,
        project_name="Test Job Project",
        description="Test description",
    )

    # Verify job and project creation
    assert isinstance(job, Job)
    assert job.id == project.uuid
    assert "test-solver" in job.name

    # Verify API calls
    assert mocked_rabbit_rpc_client.request.call_args.args == (
        "webserver",
        "mark_project_as_job",
    )
