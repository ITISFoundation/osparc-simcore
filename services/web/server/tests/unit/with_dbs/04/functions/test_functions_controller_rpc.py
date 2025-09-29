# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from collections.abc import Callable
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.functions import (
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    ProjectFunction,
)
from models_library.basic_types import IDStr
from models_library.functions import (
    Function,
    FunctionClass,
    FunctionUserAccessRights,
    RegisteredFunction,
    SolverFunction,
)
from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionReadAccessDeniedError,
    FunctionsWriteApiAccessDeniedError,
    FunctionWriteAccessDeniedError,
)
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_register_get_delete_function(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], Function],
    logged_user: UserInfoDict,
    user_role: UserRole,
    osparc_product_name: ProductName,
    other_logged_user: UserInfoDict,
):
    function = mock_function_factory(FunctionClass.PROJECT)
    assert function.function_class == FunctionClass.PROJECT

    #  Register the function
    registered_function = await webserver_rpc_client.functions.register_function(
        function=function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None
    assert registered_function.created_at - datetime.datetime.now(
        datetime.UTC
    ) < datetime.timedelta(seconds=60)

    # Retrieve the function from the repository to verify it was saved
    saved_function = await webserver_rpc_client.functions.get_function(
        function_id=registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the saved function matches the input function
    assert saved_function.uid is not None
    assert saved_function.title == function.title
    assert saved_function.description == function.description

    # Ensure saved_function is of type ProjectFunction before accessing project_id
    assert isinstance(saved_function, ProjectFunction)
    assert saved_function.project_id == function.project_id
    assert saved_function.created_at == registered_function.created_at

    # Assert the returned function matches the expected result
    assert registered_function.title == function.title
    assert registered_function.description == function.description
    assert isinstance(registered_function, ProjectFunction)
    assert registered_function.project_id == function.project_id

    with pytest.raises(FunctionReadAccessDeniedError):
        await webserver_rpc_client.functions.get_function(
            function_id=registered_function.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    with pytest.raises(FunctionWriteAccessDeniedError):
        # Attempt to delete the function by another user
        await webserver_rpc_client.functions.delete_function(
            function_id=registered_function.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    with pytest.raises(FunctionsWriteApiAccessDeniedError):
        # Attempt to delete the function in another product
        await webserver_rpc_client.functions.delete_function(
            function_id=registered_function.uid,
            user_id=other_logged_user["id"],
            product_name="this_is_not_osparc",
        )

    # Delete the function using its ID
    await webserver_rpc_client.functions.delete_function(
        function_id=registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Attempt to retrieve the deleted function
    with pytest.raises(FunctionIDNotFoundError):
        await webserver_rpc_client.functions.get_function(
            function_id=registered_function.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_not_found(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    clean_functions: None,
):
    # Attempt to retrieve a function that does not exist
    with pytest.raises(FunctionIDNotFoundError):
        await webserver_rpc_client.functions.get_function(
            function_id=uuid4(),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_functions(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    clean_functions: None,
):
    # List functions when none are registered
    functions, _ = await webserver_rpc_client.functions.list_functions(
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list is empty
    assert len(functions) == 0

    # Register a function first
    mock_function = ProjectFunction(
        title="Test Function",
        description="A test function",
        input_schema=JSONFunctionInputSchema(),
        output_schema=JSONFunctionOutputSchema(),
        project_id=uuid4(),
        default_inputs=None,
    )
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # List functions
    functions, _ = await webserver_rpc_client.functions.list_functions(
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered function
    assert len(functions) > 0
    assert any(f.uid == registered_function.uid for f in functions)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_functions_mixed_user(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], ProjectFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    other_logged_user: UserInfoDict,
    add_user_function_api_access_rights: None,
):
    function = mock_function_factory(FunctionClass.PROJECT)
    # Register a function for the logged user
    registered_functions = [
        await webserver_rpc_client.functions.register_function(
            function=function,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        for _ in range(2)
    ]

    # List functions for the other logged user
    other_functions, _ = await webserver_rpc_client.functions.list_functions(
        pagination_limit=10,
        pagination_offset=0,
        user_id=other_logged_user["id"],
        product_name=osparc_product_name,
    )
    # Assert the list contains only the logged user's function
    assert len(other_functions) == 0

    # Register a function for another user
    other_registered_function = [
        await webserver_rpc_client.functions.register_function(
            function=function,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )
        for _ in range(3)
    ]

    # List functions for the logged user
    functions, _ = await webserver_rpc_client.functions.list_functions(
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    # Assert the list contains only the logged user's function
    assert len(functions) == 2
    assert all(f.uid in [rf.uid for rf in registered_functions] for f in functions)

    other_functions, _ = await webserver_rpc_client.functions.list_functions(
        pagination_limit=10,
        pagination_offset=0,
        user_id=other_logged_user["id"],
        product_name=osparc_product_name,
    )
    # Assert the list contains only the other user's functions
    assert len(other_functions) == 3
    assert all(
        f.uid in [orf.uid for orf in other_registered_function] for f in other_functions
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "order_by",
    [
        None,
        OrderBy(field=IDStr("uid"), direction=OrderDirection.ASC),
        OrderBy(field=IDStr("uid"), direction=OrderDirection.DESC),
    ],
)
@pytest.mark.parametrize(
    "test_pagination_limit, test_pagination_offset",
    [
        (5, 0),
        (2, 2),
        (12, 4),
    ],
)
async def test_list_functions_with_pagination_ordering(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], ProjectFunction],
    clean_functions: None,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
    order_by: OrderBy | None,
    test_pagination_limit: int,
    test_pagination_offset: int,
):
    # Register multiple functions
    TOTAL_FUNCTIONS = 10
    registered_functions = [
        await webserver_rpc_client.functions.register_function(
            function=mock_function_factory(FunctionClass.PROJECT),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        for _ in range(TOTAL_FUNCTIONS)
    ]

    # List functions with pagination
    functions, page_info = await webserver_rpc_client.functions.list_functions(
        pagination_limit=test_pagination_limit,
        pagination_offset=test_pagination_offset,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        order_by=order_by,
    )

    # Assert the list contains the correct number of functions
    assert len(functions) == min(
        test_pagination_limit, max(0, TOTAL_FUNCTIONS - test_pagination_offset)
    )
    assert all(f.uid in [rf.uid for rf in registered_functions] for f in functions)
    assert page_info.count == len(functions)
    assert page_info.total == TOTAL_FUNCTIONS

    # Verify the functions are sorted correctly based on the order_by parameter
    if order_by:
        field = order_by.field
        direction = order_by.direction
        sorted_functions = sorted(
            functions,
            key=lambda f: getattr(f, field),
            reverse=(direction == OrderDirection.DESC),
        )
        assert functions == sorted_functions


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_functions_search(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], ProjectFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    function = mock_function_factory(FunctionClass.PROJECT)
    assert function.function_class == FunctionClass.PROJECT

    mock_function_dummy1 = function.model_copy()
    mock_function_dummy1.title = "Function TitleDummy1"
    mock_function_dummy1.description = "Function DescriptionDummy1"

    mock_function_dummy2 = function.model_copy()
    mock_function_dummy2.title = "Function TitleDummy2"
    mock_function_dummy2.description = "Function DescriptionDummy2"

    registered_functions = {}
    for function in [mock_function_dummy1, mock_function_dummy2]:
        registered_functions[function.title] = []
        for _ in range(5):
            registered_functions[function.title].append(
                await webserver_rpc_client.functions.register_function(
                    function=function,
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                )
            )

    for search_term, expected_number in [("Dummy", 10), ("Dummy2", 5)]:
        # Search for the function by title
        functions, _ = await webserver_rpc_client.functions.list_functions(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            search_by_function_title=search_term,
            pagination_limit=10,
            pagination_offset=0,
        )

        # Assert the function is found
        assert len(functions) == expected_number
        if search_term == "Dummy2":
            assert functions[0].uid in [
                function.uid
                for function in registered_functions[mock_function_dummy2.title]
            ]

    for search_term, expected_number in [
        ("Dummy", 10),
        ("Dummy2", 5),
        (str(registered_functions[mock_function_dummy2.title][0].uid)[:8], 1),
        ("DescriptionDummy2", 5),
    ]:
        # Search for the function by name, description, or UUID (multi-column search)
        functions, _ = await webserver_rpc_client.functions.list_functions(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            search_by_multi_columns=search_term,
            pagination_limit=10,
            pagination_offset=0,
        )

        # Assert the function is found
        assert len(functions) == expected_number
        if search_term == "Dummy2":
            assert functions[0].uid in [
                function.uid
                for function in registered_functions[mock_function_dummy2.title]
            ]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_functions_with_filters(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], ProjectFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    N_OF_PROJECT_FUNCTIONS = 3
    N_OF_SOLVER_FUNCTIONS = 4
    # Register the function first
    registered_functions = [
        await webserver_rpc_client.functions.register_function(
            function=mock_function_factory(FunctionClass.PROJECT),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        for _ in range(N_OF_PROJECT_FUNCTIONS)
    ]

    solver_function = SolverFunction(
        title="Solver Function",
        description="A function that solves problems",
        function_class=FunctionClass.SOLVER,
        input_schema=JSONFunctionInputSchema(),
        output_schema=JSONFunctionOutputSchema(),
        default_inputs=None,
        solver_key="simcore/services/comp/foo.bar-baz_/sub-dir_1/my-service1",
        solver_version="0.0.0",
    )
    registered_functions.extend(
        [
            await webserver_rpc_client.functions.register_function(
                function=solver_function,
                user_id=logged_user["id"],
                product_name=osparc_product_name,
            )
            for _ in range(N_OF_SOLVER_FUNCTIONS)
        ]
    )

    for function_class in [FunctionClass.PROJECT, FunctionClass.SOLVER]:
        # List functions with filters
        functions, _ = await webserver_rpc_client.functions.list_functions(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            filter_by_function_class=function_class,
            pagination_limit=10,
            pagination_offset=0,
        )

        # Assert the function is found
        assert len(functions) == (
            N_OF_PROJECT_FUNCTIONS
            if function_class == FunctionClass.PROJECT
            else N_OF_SOLVER_FUNCTIONS
        )
        assert all(
            function.uid in [f.uid for f in registered_functions]
            for function in functions
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_update_function_title(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Update the function's title
    updated_title = "Updated Function Title"
    registered_function.title = updated_title
    updated_function = await webserver_rpc_client.functions.update_function_title(
        function_id=registered_function.uid,
        title=updated_title,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert isinstance(updated_function, ProjectFunction)
    assert updated_function.uid == registered_function.uid
    # Assert the updated function's title matches the new title
    assert updated_function.title == updated_title

    # Update the function's title by other user
    updated_title = "Updated Function Title by Other User"
    registered_function.title = updated_title
    with pytest.raises(FunctionReadAccessDeniedError):
        updated_function = await webserver_rpc_client.functions.update_function_title(
            function_id=registered_function.uid,
            title=updated_title,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_update_function_description(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Update the function's description
    updated_description = "Updated Function Description"
    registered_function.description = updated_description
    updated_function = await webserver_rpc_client.functions.update_function_description(
        function_id=registered_function.uid,
        description=updated_description,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert isinstance(updated_function, ProjectFunction)
    assert updated_function.uid == registered_function.uid
    # Assert the updated function's description matches the new description
    assert updated_function.description == updated_description


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_input_schema(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Retrieve the input schema using its ID
    input_schema = await webserver_rpc_client.functions.get_function_input_schema(
        function_id=registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the input schema matches the registered function's input schema
    assert input_schema == registered_function.input_schema


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_output_schema(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Retrieve the output schema using its ID
    output_schema = await webserver_rpc_client.functions.get_function_output_schema(
        function_id=registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the output schema matches the registered function's output schema
    assert output_schema == registered_function.output_schema


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_delete_function(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_user_permissions(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    mock_function_factory: Callable[[FunctionClass], RegisteredFunction],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=mock_function_factory(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    # Retrieve the user permissions for the function
    user_permissions = (
        await webserver_rpc_client.functions.get_function_user_permissions(
            function_id=registered_function.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
    )

    # Assert the user permissions match the expected permissions
    assert user_permissions == FunctionUserAccessRights(
        user_id=logged_user["id"],
        read=True,
        write=True,
        execute=True,
    )
