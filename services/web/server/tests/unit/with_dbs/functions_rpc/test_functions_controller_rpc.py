# pylint: disable=redefined-outer-name
from uuid import uuid4

import pytest
import simcore_service_webserver.functions._functions_controller_rpc as functions_rpc
from aiohttp import web
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionInputSchema,
    FunctionJobCollection,
    FunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
)


@pytest.fixture
def mock_function() -> Function:
    return ProjectFunction(
        uid=None,
        title="Test Function",
        description="A test function",
        input_schema=FunctionInputSchema(
            schema_dict={"type": "object", "properties": {"input1": {"type": "string"}}}
        ),
        output_schema=FunctionOutputSchema(
            schema_dict={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ),
        project_id=uuid4(),
        default_inputs=None,
    )


@pytest.mark.asyncio
async def test_register_function(client, mock_function):
    # Register the function
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None
    # Retrieve the function from the repository to verify it was saved
    saved_function = await functions_rpc.get_function(
        app=client.app, function_id=registered_function.uid
    )

    # Assert the saved function matches the input function
    assert saved_function.uid is not None
    assert saved_function.title == mock_function.title
    assert saved_function.description == mock_function.description

    # Ensure saved_function is of type ProjectFunction before accessing project_id
    assert isinstance(saved_function, ProjectFunction)
    assert saved_function.project_id == mock_function.project_id

    # Assert the returned function matches the expected result
    assert registered_function.title == mock_function.title
    assert registered_function.description == mock_function.description
    assert isinstance(registered_function, ProjectFunction)
    assert registered_function.project_id == mock_function.project_id


@pytest.mark.asyncio
async def test_get_function(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # Retrieve the function using its ID
    retrieved_function = await functions_rpc.get_function(
        app=client.app, function_id=registered_function.uid
    )

    # Assert the retrieved function matches the registered function
    assert retrieved_function.uid == registered_function.uid
    assert retrieved_function.title == registered_function.title
    assert retrieved_function.description == registered_function.description

    # Ensure retrieved_function is of type ProjectFunction before accessing project_id
    assert isinstance(retrieved_function, ProjectFunction)
    assert isinstance(registered_function, ProjectFunction)
    assert retrieved_function.project_id == registered_function.project_id


@pytest.mark.asyncio
async def test_get_function_not_found(client):
    # Attempt to retrieve a function that does not exist
    with pytest.raises(web.HTTPNotFound):
        await functions_rpc.get_function(app=client.app, function_id=uuid4())


@pytest.mark.asyncio
async def test_list_functions(client):
    # Register a function first
    mock_function = ProjectFunction(
        uid=None,
        title="Test Function",
        description="A test function",
        input_schema=None,
        output_schema=None,
        project_id=uuid4(),
        default_inputs=None,
    )
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # List functions
    functions = await functions_rpc.list_functions(app=client.app)

    # Assert the list contains the registered function
    assert len(functions) > 0
    assert any(f.uid == registered_function.uid for f in functions)


@pytest.mark.asyncio
async def test_get_function_input_schema(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # Retrieve the input schema using its ID
    input_schema = await functions_rpc.get_function_input_schema(
        app=client.app, function_id=registered_function.uid
    )

    # Assert the input schema matches the registered function's input schema
    assert input_schema == registered_function.input_schema


@pytest.mark.asyncio
async def test_get_function_output_schema(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # Retrieve the output schema using its ID
    output_schema = await functions_rpc.get_function_output_schema(
        app=client.app, function_id=registered_function.uid
    )

    # Assert the output schema matches the registered function's output schema
    assert output_schema == registered_function.output_schema


@pytest.mark.asyncio
async def test_delete_function(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # Delete the function using its ID
    await functions_rpc.delete_function(
        app=client.app, function_id=registered_function.uid
    )

    # Attempt to retrieve the deleted function
    with pytest.raises(web.HTTPNotFound):
        await functions_rpc.get_function(
            app=client.app, function_id=registered_function.uid
        )


@pytest.mark.asyncio
async def test_register_function_job(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        uid=None,
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
    )

    # Register the function job
    registered_job = await functions_rpc.register_function_job(
        app=client.app, function_job=function_job
    )

    # Assert the registered job matches the input job
    assert registered_job.function_uid == function_job.function_uid
    assert registered_job.inputs == function_job.inputs
    assert registered_job.outputs == function_job.outputs


@pytest.mark.asyncio
async def test_get_function_job(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        uid=None,
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
    )

    # Register the function job
    registered_job = await functions_rpc.register_function_job(
        app=client.app, function_job=function_job
    )
    assert registered_job.uid is not None

    # Retrieve the function job using its ID
    retrieved_job = await functions_rpc.get_function_job(
        app=client.app, function_job_id=registered_job.uid
    )

    # Assert the retrieved job matches the registered job
    assert retrieved_job.function_uid == registered_job.function_uid
    assert retrieved_job.inputs == registered_job.inputs
    assert retrieved_job.outputs == registered_job.outputs


@pytest.mark.asyncio
async def test_get_function_job_not_found(client):
    # Attempt to retrieve a function job that does not exist
    with pytest.raises(web.HTTPNotFound):
        await functions_rpc.get_function_job(app=client.app, function_job_id=uuid4())


@pytest.mark.asyncio
async def test_list_function_jobs(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        uid=None,
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
    )

    # Register the function job
    registered_job = await functions_rpc.register_function_job(
        app=client.app, function_job=function_job
    )

    # List function jobs
    jobs = await functions_rpc.list_function_jobs(app=client.app)

    # Assert the list contains the registered job
    assert len(jobs) > 0
    assert any(j.uid == registered_job.uid for j in jobs)


@pytest.mark.asyncio
async def test_delete_function_job(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        uid=None,
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
    )

    # Register the function job
    registered_job = await functions_rpc.register_function_job(
        app=client.app, function_job=function_job
    )
    assert registered_job.uid is not None

    # Delete the function job using its ID
    await functions_rpc.delete_function_job(
        app=client.app, function_job_id=registered_job.uid
    )

    # Attempt to retrieve the deleted job
    with pytest.raises(web.HTTPNotFound):
        await functions_rpc.get_function_job(
            app=client.app, function_job_id=registered_job.uid
        )


@pytest.mark.asyncio
async def test_function_job_collection(client, mock_function):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    registered_function_job = ProjectFunctionJob(
        uid=None,
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
    )
    # Register the function job
    function_job_ids = []
    for _ in range(3):
        registered_function_job = ProjectFunctionJob(
            uid=None,
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs={"input1": "value1"},
            outputs={"output1": "result1"},
        )
        # Register the function job
        registered_job = await functions_rpc.register_function_job(
            app=client.app, function_job=registered_function_job
        )
        assert registered_job.uid is not None
        function_job_ids.append(registered_job.uid)

    function_job_collection = FunctionJobCollection(
        uid=None,
        title="Test Function Job Collection",
        description="A test function job collection",
        job_ids=function_job_ids,
    )

    # Register the function job collection
    registered_collection = await functions_rpc.register_function_job_collection(
        app=client.app, function_job_collection=function_job_collection
    )
    assert registered_collection.uid is not None

    # Assert the registered collection matches the input collection
    assert registered_collection.job_ids == function_job_ids

    await functions_rpc.delete_function_job_collection(
        app=client.app, function_job_collection_id=registered_collection.uid
    )
    # Attempt to retrieve the deleted collection
    with pytest.raises(web.HTTPNotFound):
        await functions_rpc.get_function_job(
            app=client.app, function_job_id=registered_collection.uid
        )


# @pytest.mark.asyncio
# async def test_find_cached_function_job_project_class(
#     mock_app, mock_function_id, mock_function_inputs
# ):
#     mock_function_job = AsyncMock()
#     mock_function_job.function_class = FunctionClass.project
#     mock_function_job.uuid = "mock-uuid"
#     mock_function_job.title = "mock-title"
#     mock_function_job.function_uuid = "mock-function-uuid"
#     mock_function_job.inputs = {"key": "value"}
#     mock_function_job.class_specific_data = {"project_job_id": "mock-project-job-id"}

#     with patch(
#         "simcore_service_webserver.functions._functions_repository.find_cached_function_job",
#         return_value=mock_function_job,
#     ):
#         result = await find_cached_function_job(
#             app=mock_app, function_id=mock_function_id, inputs=mock_function_inputs
#         )

#     assert isinstance(result, ProjectFunctionJob)
#     assert result.uid == "mock-uuid"
#     assert result.title == "mock-title"
#     assert result.function_uid == "mock-function-uuid"
#     assert result.inputs == {"key": "value"}
#     assert result.project_job_id == "mock-project-job-id"


# @pytest.mark.asyncio
# async def test_find_cached_function_job_solver_class(
#     mock_app, mock_function_id, mock_function_inputs
# ):
#     mock_function_job = AsyncMock()
#     mock_function_job.function_class = FunctionClass.solver
#     mock_function_job.uuid = "mock-uuid"
#     mock_function_job.title = "mock-title"
#     mock_function_job.function_uuid = "mock-function-uuid"
#     mock_function_job.inputs = {"key": "value"}
#     mock_function_job.class_specific_data = {"solver_job_id": "mock-solver-job-id"}

#     with patch(
#         "simcore_service_webserver.functions._functions_repository.find_cached_function_job",
#         return_value=mock_function_job,
#     ):
#         result = await find_cached_function_job(
#             app=mock_app, function_id=mock_function_id, inputs=mock_function_inputs
#         )

#     assert isinstance(result, SolverFunctionJob)
#     assert result.uid == "mock-uuid"
#     assert result.title == "mock-title"
#     assert result.function_uid == "mock-function-uuid"
#     assert result.inputs == {"key": "value"}
#     assert result.solver_job_id == "mock-solver-job-id"


# @pytest.mark.asyncio
# async def test_find_cached_function_job_none(mock_app, mock_function_id, mock_function_inputs):
#     with patch(
#         "simcore_service_webserver.functions._functions_repository.find_cached_function_job",
#         return_value=None,
#     ):
#         result = await find_cached_function_job(
#             app=mock_app, function_id=mock_function_id, inputs=mock_function_inputs
#         )

#     assert result is None


# @pytest.mark.asyncio
# async def test_find_cached_function_job_unsupported_class(
#     mock_app, mock_function_id, mock_function_inputs
# ):
#     mock_function_job = AsyncMock()
#     mock_function_job.function_class = "unsupported_class"

#     with patch(
#         "simcore_service_webserver.functions._functions_repository.find_cached_function_job",
#         return_value=mock_function_job,
#     ):
#         with pytest.raises(TypeError, match="Unsupported function class:"):
#             await find_cached_function_job(
#                 app=mock_app, function_id=mock_function_id, inputs=mock_function_inputs
#             )
