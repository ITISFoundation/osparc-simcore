# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid

import pytest
from faker import Faker
from models_library.api_schemas_webserver.projects_nodes import NodeOutputs
from pytest_mock import MockerFixture, MockType
from simcore_service_api_server._service_studies import StudyService
from simcore_service_api_server.models.domain.files import File
from simcore_service_api_server.models.schemas.jobs import JobInputs
from simcore_service_api_server.models.schemas.studies import StudyID


async def test_list_jobs_no_study_id(
    mocked_rpc_client: MockType,
    study_service: StudyService,
):
    # Test with default parameters
    jobs, page_meta = await study_service.list_jobs()

    assert isinstance(jobs, list)
    assert mocked_rpc_client.request.call_args.args == (
        "webserver",
        "list_projects_marked_as_jobs",
    )

    # Check pagination info
    assert page_meta.total >= 0
    assert page_meta.limit > 0
    assert page_meta.offset == 0

    # Verify proper prefix was used
    assert (
        mocked_rpc_client.request.call_args.kwargs[
            "filters"
        ].job_parent_resource_name_prefix
        == "study"
    )

    # Check pagination parameters were passed correctly
    assert mocked_rpc_client.request.call_args.kwargs["offset"] == page_meta.offset
    assert mocked_rpc_client.request.call_args.kwargs["limit"] == page_meta.limit


async def test_list_jobs_with_study_id(
    mocked_rpc_client: MockType,
    study_service: StudyService,
):
    # Test with a specific study ID
    study_id = StudyID("914c7c33-8fb6-4164-9787-7b88b5c148bf")
    jobs, page_meta = await study_service.list_jobs(filter_by_study_id=study_id)

    assert isinstance(jobs, list)

    # Verify proper prefix was used with study ID
    assert (
        mocked_rpc_client.request.call_args.kwargs[
            "filters"
        ].job_parent_resource_name_prefix
        == f"study/{study_id}"
    )

    # Check pagination parameters were passed correctly
    assert mocked_rpc_client.request.call_args.kwargs["offset"] == page_meta.offset
    assert mocked_rpc_client.request.call_args.kwargs["limit"] == page_meta.limit


@pytest.fixture
def job_inputs():
    return JobInputs(values={"param1": "value1", "param2": 42})


@pytest.fixture
def mock_project(mocker: MockerFixture):
    """Creates a mock project with a file-picker node in its workbench"""
    mock_project = mocker.MagicMock()
    mock_project.uuid = uuid.uuid4()

    # Create a file-picker node mock
    node_id = str(uuid.uuid4())
    mock_node = mocker.MagicMock()
    mock_node.key = "simcore/services/frontend/file-picker"
    mock_node.outputs = {}
    mock_node.label = "test_file_picker"

    # Set up workbench with the node
    mock_project.workbench = {node_id: mock_node}

    return {
        "project": mock_project,
        "node_id": node_id,
        "node": mock_node,
    }


async def test_create_job(
    study_service: StudyService,
    job_inputs: JobInputs,
    mock_project: dict,
    mocker: MockerFixture,
    faker: Faker,
):
    """Tests creating a job from a study"""
    # Setup
    study_id = StudyID(faker.uuid4())

    # Mock the webserver_api.clone_project to return our mock project
    study_service.webserver_api.clone_project = mocker.AsyncMock(
        return_value=mock_project["project"]
    )

    # Mock other necessary methods
    study_service.webserver_api.patch_project = mocker.AsyncMock()
    study_service.webserver_api.get_project_inputs = mocker.AsyncMock(return_value={})
    study_service.webserver_api.update_node_outputs = mocker.AsyncMock()
    study_service.webserver_api.update_project_inputs = mocker.AsyncMock()
    study_service.wb_api_rpc.mark_project_as_job = mocker.AsyncMock()

    # Execute
    job = await study_service.create_job(
        study_id=study_id,
        job_inputs=job_inputs,
    )

    # Assert
    # Check that the job was created and has the expected properties
    assert job is not None

    # Verify clone_project was called correctly
    study_service.webserver_api.clone_project.assert_awaited_once_with(
        project_id=study_id,
        hidden=True,
        parent_project_uuid=None,
        parent_node_id=None,
    )

    # Verify patch_project was called to update the job name
    study_service.webserver_api.patch_project.assert_awaited_once()
    assert (
        study_service.webserver_api.patch_project.call_args[1]["project_id"] == job.id
    )

    # Verify mark_project_as_job was called
    study_service.wb_api_rpc.mark_project_as_job.assert_awaited_once()
    assert (
        study_service.wb_api_rpc.mark_project_as_job.call_args[1]["user_id"]
        == study_service.user_id
    )
    assert (
        study_service.wb_api_rpc.mark_project_as_job.call_args[1]["product_name"]
        == study_service.product_name
    )
    assert (
        study_service.wb_api_rpc.mark_project_as_job.call_args[1]["project_uuid"]
        == job.id
    )


async def test_create_job_with_inputs(
    study_service: StudyService,
    mock_project: dict,
    mocker: MockerFixture,
    faker: Faker,
):
    """Tests creating a job with inputs that are processed properly"""
    # Setup
    study_id = StudyID(faker.uuid4())

    job_inputs = JobInputs(
        values={
            "param1": "test_value",
            "file_param": File.model_json_schema()["examples"][0],
        }
    )

    # Mock clone_project
    study_service.webserver_api.clone_project = mocker.AsyncMock(
        return_value=mock_project["project"]
    )

    # Mock other methods
    study_service.webserver_api.patch_project = mocker.AsyncMock()
    study_service.webserver_api.get_project_inputs = mocker.AsyncMock(return_value={})
    study_service.webserver_api.update_node_outputs = mocker.AsyncMock()
    study_service.webserver_api.update_project_inputs = mocker.AsyncMock()
    study_service.wb_api_rpc.mark_project_as_job = mocker.AsyncMock()

    # Mock get_project_and_file_inputs_from_job_inputs to return test data
    project_inputs = {"param1": "test_value"}
    file_inputs = {"test_file_picker": File.model_json_schema()["examples"][0]}

    mocker.patch(
        "simcore_service_api_server.services_http.study_job_models_converters.get_project_and_file_inputs_from_job_inputs",
        return_value=(project_inputs, file_inputs),
    )

    # Execute
    job = await study_service.create_job(
        study_id=study_id,
        job_inputs=job_inputs,
    )

    # Assert
    assert job is not None

    # Verify update_node_outputs was called for file inputs
    study_service.webserver_api.update_node_outputs.assert_awaited_once()
    call_args = study_service.webserver_api.update_node_outputs.call_args[1]
    assert call_args["project_id"] == mock_project["project"].uuid
    assert isinstance(call_args["new_node_outputs"], NodeOutputs)
    assert "outFile" in call_args["new_node_outputs"].outputs

    # Verify update_project_inputs was called with project inputs
    study_service.webserver_api.update_project_inputs.assert_awaited_once_with(
        project_id=mock_project["project"].uuid,
        new_inputs=project_inputs,
    )
