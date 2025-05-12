# pylint: disable=redefined-outer-name
from uuid import uuid4

import pytest
import simcore_service_webserver.functions._functions_controller_rpc as functions_rpc
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionIDNotFoundError,
    FunctionJobCollection,
    FunctionJobIDNotFoundError,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
)


@pytest.fixture
def mock_function() -> Function:
    return ProjectFunction(
        title="Test Function",
        description="A test function",
        input_schema=JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "string"}},
            }
        ),
        output_schema=JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ),
        project_id=uuid4(),
        default_inputs=None,
    )


@pytest.fixture
async def clean_functions(client):
    # This function is a placeholder for the actual implementation
    # that deletes all registered functions from the database.
    functions, _ = await functions_rpc.list_functions(
        app=client.app, pagination_limit=100, pagination_offset=0
    )
    for function in functions:
        assert function.uid is not None
        await functions_rpc.delete_function(app=client.app, function_id=function.uid)


async def test_register_function(client, mock_function: ProjectFunction):
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


async def test_get_function(client, mock_function: ProjectFunction):
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


async def test_get_function_not_found(client):
    # Attempt to retrieve a function that does not exist
    with pytest.raises(FunctionIDNotFoundError):
        await functions_rpc.get_function(app=client.app, function_id=uuid4())


async def test_list_functions(client):
    # Register a function first
    mock_function = ProjectFunction(
        title="Test Function",
        description="A test function",
        input_schema=JSONFunctionInputSchema(),
        output_schema=JSONFunctionOutputSchema(),
        project_id=uuid4(),
        default_inputs=None,
    )
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # List functions
    functions, _ = await functions_rpc.list_functions(
        app=client.app, pagination_limit=10, pagination_offset=0
    )

    # Assert the list contains the registered function
    assert len(functions) > 0
    assert any(f.uid == registered_function.uid for f in functions)


@pytest.mark.usefixtures("clean_functions")
async def test_list_functions_empty(client):
    # List functions when none are registered
    functions, _ = await functions_rpc.list_functions(
        app=client.app, pagination_limit=10, pagination_offset=0
    )

    # Assert the list is empty
    assert len(functions) == 0


@pytest.mark.usefixtures("clean_functions")
async def test_list_functions_with_pagination(client, mock_function):
    # Register multiple functions
    TOTAL_FUNCTIONS = 3
    for _ in range(TOTAL_FUNCTIONS):
        await functions_rpc.register_function(app=client.app, function=mock_function)

    functions, page_info = await functions_rpc.list_functions(
        app=client.app, pagination_limit=2, pagination_offset=0
    )

    # List functions with pagination
    functions, page_info = await functions_rpc.list_functions(
        app=client.app, pagination_limit=2, pagination_offset=0
    )

    # Assert the list contains the correct number of functions
    assert len(functions) == 2
    assert page_info.count == 2
    assert page_info.total == TOTAL_FUNCTIONS

    # List the next page of functions
    functions, page_info = await functions_rpc.list_functions(
        app=client.app, pagination_limit=2, pagination_offset=2
    )

    # Assert the list contains the correct number of functions
    assert len(functions) == 1
    assert page_info.count == 1
    assert page_info.total == TOTAL_FUNCTIONS


async def test_get_function_input_schema(client, mock_function: ProjectFunction):
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


async def test_get_function_output_schema(client, mock_function: ProjectFunction):
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


async def test_delete_function(client, mock_function: ProjectFunction):
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
    with pytest.raises(FunctionIDNotFoundError):
        await functions_rpc.get_function(
            app=client.app, function_id=registered_function.uid
        )


async def test_register_function_job(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
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


async def test_get_function_job(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
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


async def test_get_function_job_not_found(client):
    # Attempt to retrieve a function job that does not exist
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(app=client.app, function_job_id=uuid4())


async def test_list_function_jobs(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
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
    jobs, _ = await functions_rpc.list_function_jobs(
        app=client.app, pagination_limit=10, pagination_offset=0
    )

    # Assert the list contains the registered job
    assert len(jobs) > 0
    assert any(j.uid == registered_job.uid for j in jobs)


async def test_delete_function_job(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
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
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(
            app=client.app, function_job_id=registered_job.uid
        )


async def test_function_job_collection(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    registered_function_job = ProjectFunctionJob(
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
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(
            app=client.app, function_job_id=registered_collection.uid
        )


async def test_list_function_job_collections(client, mock_function: ProjectFunction):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        app=client.app, function=mock_function
    )
    assert registered_function.uid is not None

    # Create a function job collection
    function_job_ids = []
    for _ in range(3):
        registered_function_job = ProjectFunctionJob(
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
        title="Test Function Job Collection",
        description="A test function job collection",
        job_ids=function_job_ids,
    )

    # Register the function job collection
    registered_collections = [
        await functions_rpc.register_function_job_collection(
            app=client.app, function_job_collection=function_job_collection
        )
        for _ in range(3)
    ]
    assert all(
        registered_collection.uid is not None
        for registered_collection in registered_collections
    )

    # List function job collections
    collections, _ = await functions_rpc.list_function_job_collections(
        app=client.app, pagination_limit=1, pagination_offset=1
    )

    # Assert the list contains the registered collection
    assert len(collections) == 1
    assert collections[0].uid == registered_collections[1].uid
