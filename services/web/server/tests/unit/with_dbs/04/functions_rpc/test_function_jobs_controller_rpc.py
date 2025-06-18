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
from models_library.functions_errors import (
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
)
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_login import UserInfoDict
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
async def test_list_function_jobs_for_functionid(
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
    assert len(jobs) > 0
    assert len(jobs) == 3
    assert all(j.function_uid == first_registered_function.uid for j in jobs)


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
