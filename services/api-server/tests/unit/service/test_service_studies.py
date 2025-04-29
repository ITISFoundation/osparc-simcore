# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pytest_mock import MockType
from simcore_service_api_server._service_studies import StudyService
from simcore_service_api_server.models.schemas.studies import StudyID


async def test_list_jobs_no_study_id(
    study_service: StudyService,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    # Test with default parameters
    jobs, page_meta = await study_service.list_jobs()

    assert isinstance(jobs, list)
    mocked_webserver_rpc_api["list_projects_marked_as_jobs"].assert_called_once()

    # Check pagination info
    assert page_meta.total >= 0
    assert page_meta.limit > 0
    assert page_meta.offset == 0

    # Verify proper prefix was used
    call_kwargs = mocked_webserver_rpc_api[
        "list_projects_marked_as_jobs"
    ].call_args.kwargs
    assert call_kwargs["job_parent_resource_name_prefix"] == "study"


async def test_list_jobs_with_study_id(
    study_service: StudyService,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    # Test with a specific study ID
    study_id = StudyID("test-study-id")
    jobs, page_meta = await study_service.list_jobs(study_id=study_id)

    assert isinstance(jobs, list)

    # Verify proper prefix was used with study ID
    call_kwargs = mocked_webserver_rpc_api[
        "list_projects_marked_as_jobs"
    ].call_args.kwargs
    assert call_kwargs["job_parent_resource_name_prefix"] == f"study/{study_id}"

    # Check pagination parameters were passed correctly
    assert call_kwargs["offset"] == 0
    assert call_kwargs["limit"] > 0
