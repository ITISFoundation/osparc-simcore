# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from collections.abc import Callable
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.functions import (
    FunctionIDString,
    FunctionJobCollection,
    ProjectFunctionJob,
)
from models_library.functions import (
    Function,
    FunctionClass,
    FunctionJobCollectionsListFilters,
    FunctionJobList,
)
from models_library.functions_errors import (
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionJobCollectionWriteAccessDeniedError,
    FunctionJobIDNotFoundError,
)
from models_library.products import ProductName
from pydantic import TypeAdapter
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_function_job_collection(
    client: TestClient,
    add_user_function_api_access_rights: None,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    user_without_function_api_access_rights: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Register the function jobs
    function_jobs = [
        ProjectFunctionJob(
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs={"input1": "value1"},
            outputs={"output1": "result1"},
            job_creation_task_id=None,
        )
        for _ in range(3)
    ]
    # Register the function jobs
    registered_jobs = await webserver_rpc_client.functions.register_function_job_batch(
        function_jobs=TypeAdapter(FunctionJobList).validate_python(function_jobs),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 3
    assert all(job.uid is not None for job in registered_jobs)
    function_job_ids = [job.uid for job in registered_jobs]

    function_job_collection = FunctionJobCollection(
        title="Test Function Job Collection",
        description="A test function job collection",
        job_ids=function_job_ids,
    )

    # Register the function job collection
    registered_collection = (
        await webserver_rpc_client.functions.register_function_job_collection(
            function_job_collection=function_job_collection,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
    )
    assert registered_collection.uid is not None
    assert registered_collection.created_at - datetime.datetime.now(
        datetime.UTC
    ) < datetime.timedelta(seconds=60)

    # Get the function job collection
    retrieved_collection = (
        await webserver_rpc_client.functions.get_function_job_collection(
            function_job_collection_id=registered_collection.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
    )
    assert retrieved_collection.uid == registered_collection.uid
    assert registered_collection.job_ids == function_job_ids

    # Test denied access for another user
    with pytest.raises(FunctionJobCollectionReadAccessDeniedError):
        await webserver_rpc_client.functions.get_function_job_collection(
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another user
    with pytest.raises(FunctionJobCollectionsReadApiAccessDeniedError):
        await webserver_rpc_client.functions.get_function_job_collection(
            function_job_collection_id=registered_collection.uid,
            user_id=user_without_function_api_access_rights["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another product
    with pytest.raises(FunctionJobCollectionsReadApiAccessDeniedError):
        await webserver_rpc_client.functions.get_function_job_collection(
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name="this_is_not_osparc",
        )

    # Attempt to delete the function job collection by another user
    with pytest.raises(FunctionJobCollectionWriteAccessDeniedError):
        await webserver_rpc_client.functions.delete_function_job_collection(
            function_job_collection_id=registered_collection.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    await webserver_rpc_client.functions.delete_function_job_collection(
        function_job_collection_id=registered_collection.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    # Attempt to retrieve the deleted collection
    with pytest.raises(FunctionJobIDNotFoundError):
        await webserver_rpc_client.functions.get_function_job(
            function_job_id=registered_collection.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_create_function_job_collection_same_function_job_uuid(
    client: TestClient,
    add_user_function_api_access_rights: None,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    user_without_function_api_access_rights: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
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
        job_creation_task_id=None,
    )
    # Register the function job
    function_job_ids = []
    registered_function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
        job_creation_task_id=None,
    )
    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job_batch(
        function_jobs=[registered_function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]
    assert registered_job.uid is not None

    function_job_ids = [registered_job.uid] * 3

    function_job_collection = FunctionJobCollection(
        title="Test Function Job Collection",
        description="A test function job collection",
        job_ids=function_job_ids,
    )

    assert function_job_collection.job_ids[0] == registered_job.uid
    assert function_job_collection.job_ids[1] == registered_job.uid
    assert function_job_collection.job_ids[2] == registered_job.uid


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_job_collections(
    client: TestClient,
    add_user_function_api_access_rights: None,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    webserver_rpc_client: WebServerRpcClient,
    clean_functions: None,
    clean_function_job_collections: None,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # List function job collections when none are registered
    collections, page_meta = (
        await webserver_rpc_client.functions.list_function_job_collections(
            pagination_limit=10,
            pagination_offset=0,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
    )

    # Assert the list is empty
    assert page_meta.count == 0
    assert page_meta.total == 0
    assert page_meta.offset == 0
    assert len(collections) == 0

    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Create a function job collection
    function_jobs = [
        ProjectFunctionJob(
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs={"input1": "value1"},
            outputs={"output1": "result1"},
            job_creation_task_id=None,
        )
        for _ in range(3)
    ]
    # Register the function jobs
    registered_jobs = await webserver_rpc_client.functions.register_function_job_batch(
        function_jobs=TypeAdapter(FunctionJobList).validate_python(function_jobs),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert all(job.uid is not None for job in registered_jobs)

    function_job_collection = FunctionJobCollection(
        title="Test Function Job Collection",
        description="A test function job collection",
        job_ids=[job.uid for job in registered_jobs],
    )

    # Register the function job collection
    registered_collections = [
        await webserver_rpc_client.functions.register_function_job_collection(
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
    collections, page_params = (
        await webserver_rpc_client.functions.list_function_job_collections(
            pagination_limit=2,
            pagination_offset=1,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
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
    webserver_rpc_client: WebServerRpcClient,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    clean_functions: None,
    clean_function_job_collections: None,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    other_registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
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
        function_jobs = [
            ProjectFunctionJob(
                function_uid=function_id,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
                job_creation_task_id=None,
            )
            for _ in range(3)
        ]
        # Register the function job
        registered_jobs = (
            await webserver_rpc_client.functions.register_function_job_batch(
                function_jobs=TypeAdapter(FunctionJobList).validate_python(
                    function_jobs
                ),
                user_id=logged_user["id"],
                product_name=osparc_product_name,
            )
        )
        assert all(job.uid for job in registered_jobs)
        function_job_ids = [job.uid for job in registered_jobs]

        function_job_collection = FunctionJobCollection(
            title="Test Function Job Collection",
            description="A test function job collection",
            job_ids=function_job_ids,
        )

        # Register the function job collection
        registered_collection = (
            await webserver_rpc_client.functions.register_function_job_collection(
                function_job_collection=function_job_collection,
                user_id=logged_user["id"],
                product_name=osparc_product_name,
            )
        )
        registered_collections.append(registered_collection)

    # List function job collections with a specific function ID
    collections, page_meta = (
        await webserver_rpc_client.functions.list_function_job_collections(
            pagination_limit=10,
            pagination_offset=1,
            filters=FunctionJobCollectionsListFilters(
                has_function_id=FunctionIDString(registered_function.uid)
            ),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
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
