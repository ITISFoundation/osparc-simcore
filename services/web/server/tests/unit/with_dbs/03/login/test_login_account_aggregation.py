# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole, UserStatus
from models_library.products import ProductName
from simcore_service_webserver.groups import groups_service
from simcore_service_webserver.login import (
    _account_aggregation_service,
    _auth_service,
)
from simcore_service_webserver.login.errors import UserAlreadyRegisteredError
from simcore_service_webserver.products import products_service


async def test_create_account_creates_active_admin_in_product_group(
    client: TestClient,
    default_product_name: ProductName,
    user_email: str,
    user_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    app = client.app

    user = await _account_aggregation_service.create_account(
        app,
        email=user_email,
        password=user_password,
        role=UserRole.ADMIN,
        product_name=default_product_name,
    )

    created = await _auth_service.get_user_or_none(app, email=user_email)
    assert created is not None
    assert created["id"] == user["id"]
    assert created["role"] == UserRole.ADMIN.value
    assert created["status"] == UserStatus.ACTIVE.value

    # is member of the product group
    product = products_service.get_product(app, product_name=default_product_name)
    assert product.group_id is not None
    assert await groups_service.is_user_in_group(app, user_id=user["id"], group_id=product.group_id)


async def test_create_account_with_existing_email_raises(
    client: TestClient,
    default_product_name: ProductName,
    user_email: str,
    user_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    app = client.app

    await _account_aggregation_service.create_account(
        app,
        email=user_email,
        password=user_password,
        role=UserRole.ADMIN,
        product_name=default_product_name,
    )

    with pytest.raises(UserAlreadyRegisteredError):
        await _account_aggregation_service.create_account(
            app,
            email=user_email,
            password=user_password,
            role=UserRole.ADMIN,
            product_name=default_product_name,
        )
