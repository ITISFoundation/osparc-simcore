# pylint: disable=unused-argument

from collections.abc import Callable

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.functions import (
    FunctionClass,
    FunctionGroupAccessRights,
    RegisteredFunction,
)
from models_library.functions_errors import FunctionReadAccessDeniedError
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.functions import _functions_service

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_set_and_remove_group_permissions(
    client: TestClient,
    user_role: UserRole,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    create_fake_function_obj: Callable[[FunctionClass], RegisteredFunction],
    clean_functions: None,
) -> None:
    # Register the function
    registered_function = await _functions_service.register_function(
        app=client.app,
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Test if registering user can access the function
    returned_function = await _functions_service.get_function(
        app=client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        function_id=registered_function.uid,
    )
    assert returned_function.uid == registered_function.uid

    # Test if non-registering user cannot access the function
    with pytest.raises(FunctionReadAccessDeniedError):
        await _functions_service.get_function(
            app=client.app,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
            function_id=registered_function.uid,
        )

    group_permissions = FunctionGroupAccessRights(
        group_id=int(other_logged_user["primary_gid"]),
        read=True,
        write=True,
        execute=False,
    )

    # Give non-registering user group access
    updated_group_permissions = await _functions_service.set_function_group_permissions(
        app=client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        function_id=registered_function.uid,
        permissions=group_permissions,
    )

    assert updated_group_permissions == group_permissions

    # Test if non-registering user can access the function
    returned_function = await _functions_service.get_function(
        app=client.app,
        user_id=other_logged_user["id"],
        product_name=osparc_product_name,
        function_id=registered_function.uid,
    )
    assert returned_function.uid == registered_function.uid

    # Remove non-registering user group access
    await _functions_service.remove_function_group_permissions(
        app=client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        permission_group_id=int(other_logged_user["primary_gid"]),
        function_id=registered_function.uid,
    )

    # Test if non-registering user cannot access the function
    with pytest.raises(FunctionReadAccessDeniedError):
        await _functions_service.get_function(
            app=client.app,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
            function_id=registered_function.uid,
        )
