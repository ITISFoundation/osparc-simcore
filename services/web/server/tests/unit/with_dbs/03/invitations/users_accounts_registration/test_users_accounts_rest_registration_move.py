# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.rest_error import ErrorGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.PRODUCT_OWNER


async def test_move_user_account_unknown_product_returns_409(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    """Passing an unknown new_product_name in the move endpoint must yield 409 Conflict."""
    assert client.app
    invalid_product_name = "nonexistent-product-xyz"

    # 1. Create a pending pre-registration so the move operation can be attempted
    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=account_request_form,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    pre_reg_data, _ = await assert_status(resp, status.HTTP_200_OK)
    pre_registration_id: int = pre_reg_data["preRegistrationId"]

    # 2. Move towards a product that does not exist -> should be a conflict (409)
    url = client.app.router["move_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:move"

    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "preRegistrationId": pre_registration_id,
            "newProductName": invalid_product_name,
        },
    )
    _, error = await assert_status(resp, status.HTTP_409_CONFLICT)

    error_model = ErrorGet.model_validate(error)
    assert error_model.status == status.HTTP_409_CONFLICT
    assert error_model.message == f"Invalid product '{invalid_product_name}'. The specified product does not exist."
