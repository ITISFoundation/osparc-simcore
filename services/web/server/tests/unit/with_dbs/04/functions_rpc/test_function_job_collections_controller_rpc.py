# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.functions import (
    FunctionIDString,
    FunctionJobCollection,
    ProjectFunction,
    ProjectFunctionJob,
)
from models_library.functions import FunctionJobCollectionsListFilters
from models_library.functions_errors import (
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionJobIDNotFoundError,
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
async def test_function_job_collection(
    client: TestClient,
    add_user_function_api_access_rights: None,
    mock_function: ProjectFunction,
    rpc_client: RabbitMQRPCClient,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    user_without_function_api_access_rights: UserInfoDict,
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
            rabbitmq_rpc_client=rpc_client,
            function_job=registered_function_job,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
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
        rabbitmq_rpc_client=rpc_client,
        function_job_collection=function_job_collection,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_collection.uid is not None
    assert registered_collection.created_at - datetime.datetime.now(
        datetime.UTC
    ) < datetime.timedelta(seconds=60)

    # Get the function job collection
    retrieved_collection = await functions_rpc.get_function_job_collection(
        rabbitmq_rpc_client=rpc_client,
        function_job_collection_id=registered_collection.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert retrieved_collection.uid == registered_collection.uid
    assert registered_collection.job_ids == function_job_ids

    # Test denied access for another user
    with pytest.raises(FunctionJobCollectionReadAccessDeniedError):
        await functions_rpc.get_function_job_collection(
            rabbitmq_rpc_client=rpc_client,
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another user
    with pytest.raises(FunctionJobCollectionsReadApiAccessDeniedError):
        await functions_rpc.get_function_job_collection(
            rabbitmq_rpc_client=rpc_client,
            function_job_collection_id=registered_collection.uid,
            user_id=user_without_function_api_access_rights["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another product
    with pytest.raises(FunctionJobCollectionsReadApiAccessDeniedError):
        await functions_rpc.get_function_job_collection(
            rabbitmq_rpc_client=rpc_client,
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name="this_is_not_osparc",
        )

    # Attempt to delete the function job collection by another user
    with pytest.raises(FunctionJobCollectionReadAccessDeniedError):
        await functions_rpc.delete_function_job_collection(
            rabbitmq_rpc_client=rpc_client,
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    await functions_rpc.delete_function_job_collection(
        rabbitmq_rpc_client=rpc_client,
        function_job_collection_id=registered_collection.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    # Attempt to retrieve the deleted collection
    with pytest.raises(FunctionJobIDNotFoundError):
        await functions_rpc.get_function_job(
            rabbitmq_rpc_client=rpc_client,
            function_job_id=registered_collection.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_job_collections(
    client: TestClient,
    add_user_function_api_access_rights: None,
    mock_function: ProjectFunction,
    rpc_client: RabbitMQRPCClient,
    clean_functions: None,
    clean_function_job_collections: None,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # List function job collections when none are registered
    collections, page_meta = await functions_rpc.list_function_job_collections(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list is empty
    assert page_meta.count == 0
    assert page_meta.total == 0
    assert page_meta.offset == 0
    assert len(collections) == 0

    # Register the function first
    registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
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
            rabbitmq_rpc_client=rpc_client,
            function_job=registered_function_job,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
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
            rabbitmq_rpc_client=rpc_client,
            function_job_collection=function_job_collection,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        for _ in range(3)
    ]
    assert all(
        registered_collection.uid is not None
        for registered_collection in registered_collections
    )

    # List function job collections
    collections, page_params = await functions_rpc.list_function_job_collections(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=2,
        pagination_offset=1,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered collection
    assert page_params.count == 2
    assert page_params.total == 3
    assert page_params.offset == 1
    assert len(collections) == 2
    assert collections[0].uid in [
        collection.uid for collection in registered_collections
    ]
    assert collections[1].uid in [
        collection.uid for collection in registered_collections
    ]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_job_collections_filtered_function_id(
    client: TestClient,
    add_user_function_api_access_rights: None,
    rpc_client: RabbitMQRPCClient,
    mock_function: ProjectFunction,
    clean_functions: None,
    clean_function_job_collections: None,
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
    other_registered_function = await functions_rpc.register_function(
        rabbitmq_rpc_client=rpc_client,
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    registered_collections = []
    for coll_i in range(5):
        if coll_i < 3:
            function_id = registered_function.uid
        else:
            function_id = other_registered_function.uid
        # Create a function job collection
        function_job_ids = []
        for _ in range(3):
            registered_function_job = ProjectFunctionJob(
                function_uid=function_id,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
            )
            # Register the function job
            registered_job = await functions_rpc.register_function_job(
                rabbitmq_rpc_client=rpc_client,
                function_job=registered_function_job,
                user_id=logged_user["id"],
                product_name=osparc_product_name,
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
            rabbitmq_rpc_client=rpc_client,
            function_job_collection=function_job_collection,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        registered_collections.append(registered_collection)

    # List function job collections with a specific function ID
    collections, page_meta = await functions_rpc.list_function_job_collections(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=10,
        pagination_offset=1,
        filters=FunctionJobCollectionsListFilters(
            has_function_id=FunctionIDString(registered_function.uid)
        ),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered collection
    assert page_meta.count == 2
    assert page_meta.total == 3
    assert page_meta.offset == 1

    assert len(collections) == 2
    assert collections[0].uid in [
        collection.uid for collection in registered_collections
    ]
    assert collections[1].uid in [
        collection.uid for collection in registered_collections
    ]
