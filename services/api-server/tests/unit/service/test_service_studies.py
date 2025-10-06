# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pytest_mock import MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.models.schemas.studies import StudyID


async def test_list_jobs_no_study_id(
    mocked_rabbit_rpc_client: MockType, job_service: JobService
):
    # Test with default parameters
    jobs, page_meta = await job_service.list_study_jobs()

    assert isinstance(jobs, list)
    assert mocked_rabbit_rpc_client.request.call_args.args == (
        "webserver",
        "list_projects_marked_as_jobs",
    )

    # Check pagination info
    assert page_meta.total >= 0
    assert page_meta.limit > 0
    assert page_meta.offset == 0

    # Verify proper prefix was used
    assert (
        mocked_rabbit_rpc_client.request.call_args.kwargs[
            "filters"
        ].job_parent_resource_name_prefix
        == "study"
    )

    # Check pagination parameters were passed correctly
    assert (
        mocked_rabbit_rpc_client.request.call_args.kwargs["offset"] == page_meta.offset
    )
    assert mocked_rabbit_rpc_client.request.call_args.kwargs["limit"] == page_meta.limit


async def test_list_jobs_with_study_id(
    mocked_rabbit_rpc_client: MockType,
    job_service: JobService,
):
    # Test with a specific study ID
    study_id = StudyID("914c7c33-8fb6-4164-9787-7b88b5c148bf")
    jobs, page_meta = await job_service.list_study_jobs(filter_by_study_id=study_id)

    assert isinstance(jobs, list)

    # Verify proper prefix was used with study ID
    assert (
        mocked_rabbit_rpc_client.request.call_args.kwargs[
            "filters"
        ].job_parent_resource_name_prefix
        == f"study/{study_id}"
    )

    # Check pagination parameters were passed correctly
    assert (
        mocked_rabbit_rpc_client.request.call_args.kwargs["offset"] == page_meta.offset
    )
    assert mocked_rabbit_rpc_client.request.call_args.kwargs["limit"] == page_meta.limit
