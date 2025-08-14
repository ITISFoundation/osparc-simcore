# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.functions import (
    ProjectFunction,
    ProjectFunctionJob,
)
from models_library.functions import FunctionJobCollection, FunctionJobStatus
from models_library.functions_errors import (
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
)
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.functions import (
    functions_rpc_interface as functions_rpc,
)

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_register_get_delete_function_job(
    client: TestClient,
    add_user_function_api_access_rights: None,
    rpc_client: RabbitMQRPCClient,
    mock_function: ProjectFunction,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
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
        rabbitmq_rpc_client=rpc_client,
        function_job=function_job,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the registered job matches the input job
    assert registered_job.function_uid == function_job.function_uid
    assert registered_job.inputs == function_job.inputs
    assert registered_job.outputs == function_job.outputs
    assert registered_job.created_at - datetime.datetime.now(
        datetime.UTC
    ) < datetime.timedelta(seconds=60)

    # Retrieve the function job using its ID
    retrieved_job = await functions_rpc.get_function_job(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the retrieved job matches the registered job
    assert retrieved_job.function_uid == registered_job.function_uid
    assert retrieved_job.inputs == registered_job.inputs
    assert retrieved_job.outputs == registered_job.outputs

    # Test denied access for another user
    with pytest.raises(FunctionJobReadAccessDeniedError):
        await functions_rpc.get_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another product
    with pytest.raises(FunctionJobsReadApiAccessDeniedError):
        await functions_rpc.get_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name="this_is_not_osparc",
        )

    with pytest.raises(FunctionJobWriteAccessDeniedError):
        # Attempt to delete the function job by another user
        await functions_rpc.delete_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Delete the function job using its ID
    await functions_rpc.delete_function_job(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Attempt to retrieve the deleted job
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=registered_job.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_job_not_found(
    client: TestClient,
    add_user_function_api_access_rights: None,
    rpc_client: RabbitMQRPCClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    clean_functions: None,
):
    # Attempt to retrieve a function job that does not exist
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=uuid4(),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_jobs(
    client: TestClient,
    add_user_function_api_access_rights: None,
    rpc_client: RabbitMQRPCClient,
    mock_function: ProjectFunction,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
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
        rabbitmq_rpc_client=rpc_client,
        function_job=function_job,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # List function jobs
    jobs, _ = await functions_rpc.list_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) > 0
    assert any(j.uid == registered_job.uid for j in jobs)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_jobs_filtering(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    mock_function: ProjectFunction,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    first_registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    second_registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    first_registered_function_jobs = []
    second_registered_function_jobs = []
    for i_job in range(6):
        if i_job < 3:
            function_job = ProjectFunctionJob(
                function_uid=first_registered_function.uid,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
            )
            # Register the function job
            first_registered_function_jobs.append(
                await functions_rpc.register_function_job(
                    rabbitmq_rpc_client=rpc_client,
                    function_job=function_job,
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                )
            )
        else:
            function_job = ProjectFunctionJob(
                function_uid=second_registered_function.uid,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
            )
            # Register the function job
            second_registered_function_jobs.append(
                await functions_rpc.register_function_job(
                    rabbitmq_rpc_client=rpc_client,
                    function_job=function_job,
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                )
            )

    function_job_collection = await functions_rpc.register_function_job_collection(
        rabbitmq_rpc_client=rpc_client,
        function_job_collection=FunctionJobCollection(
            job_ids=[
                job.uid
                for job in first_registered_function_jobs[1:2]
                + second_registered_function_jobs[0:1]
            ]
        ),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # List function jobs for a specific function ID
    jobs, _ = await functions_rpc.list_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_id=first_registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 3
    assert all(j.function_uid == first_registered_function.uid for j in jobs)

    # List function jobs for a specific function job IDs
    jobs, _ = await functions_rpc.list_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_ids=[
            job.uid
            for job in first_registered_function_jobs[0:1]
            + second_registered_function_jobs[1:2]
        ],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 2
    assert jobs[0].uid == first_registered_function_jobs[0].uid
    assert jobs[1].uid == second_registered_function_jobs[1].uid

    # List function jobs for a specific function job collection
    jobs, _ = await functions_rpc.list_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_collection_id=function_job_collection.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 2
    assert jobs[0].uid == first_registered_function_jobs[1].uid
    assert jobs[1].uid == second_registered_function_jobs[0].uid

    # List function jobs for a specific function job collection and function job id
    jobs, _ = await functions_rpc.list_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_collection_id=function_job_collection.uid,
        filter_by_function_job_ids=[first_registered_function_jobs[1].uid],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 1
    assert jobs[0].uid == first_registered_function_jobs[1].uid


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_find_cached_function_jobs(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    mock_function: ProjectFunction,
    clean_functions: None,
):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    registered_function_jobs = []
    for value in range(5):
        function_job = ProjectFunctionJob(
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs={"input1": value if value < 4 else 1},
            outputs={"output1": "result1"},
        )

        # Register the function job
        registered_job = await functions_rpc.register_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job=function_job,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        registered_function_jobs.append(registered_job)

    # Find cached function jobs
    cached_jobs = await functions_rpc.find_cached_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        function_id=registered_function.uid,
        inputs={"input1": 1},
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the cached jobs contain the registered job
    assert cached_jobs is not None
    assert len(cached_jobs) == 2
    assert {job.uid for job in cached_jobs} == {
        registered_function_jobs[1].uid,
        registered_function_jobs[4].uid,
    }

    cached_jobs = await functions_rpc.find_cached_function_jobs(
        rabbitmq_rpc_client=rpc_client,
        function_id=registered_function.uid,
        inputs={"input1": 1},
        user_id=other_logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the cached jobs does not contain the registered job for the other user
    assert cached_jobs is None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_update_function_job_status(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    mock_function: ProjectFunction,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

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
        rabbitmq_rpc_client=rpc_client,
        function_job=function_job,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    old_job_status = await functions_rpc.get_function_job_status(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert old_job_status.status == "created"

    # Update the function job status
    new_status = FunctionJobStatus(status="COMPLETED")
    updated_job_status = await functions_rpc.update_function_job_status(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        job_status=new_status,
    )

    # Assert the updated job status matches the new status
    assert updated_job_status == new_status


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_update_function_job_outputs(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    mock_function: ProjectFunction,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs=None,
    )

    # Register the function job
    registered_job = await functions_rpc.register_function_job(
        rabbitmq_rpc_client=rpc_client,
        function_job=function_job,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    received_outputs = await functions_rpc.get_function_job_outputs(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert received_outputs is None

    new_outputs = {"output1": "new_result1", "output2": "new_result2"}

    # Update the function job outputs
    updated_outputs = await functions_rpc.update_function_job_outputs(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        outputs=new_outputs,
    )

    # Assert the updated outputs match the new outputs
    assert updated_outputs == new_outputs

    # Update the function job outputs
    received_outputs = await functions_rpc.get_function_job_outputs(
        rabbitmq_rpc_client=rpc_client,
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert received_outputs == new_outputs
