# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Literal, TypedDict
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.api_schemas_webserver.users import (
    UserAccountGet,
    UserAccountProductOptionGet,
)
from models_library.products import ProductName
from models_library.rest_error import ErrorGet
from models_library.rest_pagination import Page
from pydantic import TypeAdapter
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.login import _auth_service

from .conftest import SeededUserAccountsEmails


class UserAccountsListQueryParams(TypedDict):
    review_status: Literal["PENDING", "REVIEWED"]
    registered: Literal["true", "false"]
    limit: int
    offset: int


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
async def test_list_users_accounts(  # noqa: PLR0915
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    assert client.app

    # 1. Create several pre-registered users
    pre_registered_users = []
    for _ in range(5):  # Create 5 pre-registered users
        form_data = account_request_form.copy()
        form_data["firstName"] = faker.first_name()
        form_data["lastName"] = faker.last_name()
        form_data["email"] = faker.email()

        resp = await client.post(
            "/v0/admin/user-accounts:pre-register",
            json=form_data,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        )
        pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
        pre_registered_users.append(pre_registered_data)

    # Verify all pre-registered users are in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()

    # Parse response into Page[UserForAdminGet] model
    page_model = Page[UserAccountGet].model_validate(response_json)

    # Access the items field from the paginated response
    pending_users = [user for user in page_model.data if user.account_request_status == "PENDING"]
    pending_emails = [user.email for user in pending_users]

    for pre_user in pre_registered_users:
        assert pre_user["email"] in pending_emails

    # 2. Register one of the pre-registered users: approve + create account
    registered_email = pre_registered_users[0]["email"]

    # First, preview approval to get the invitation URL
    preview_url = client.app.router["preview_approval_user_account"].url_for()
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": registered_email,
            "invitation": {"trialAccountDays": 30},
        },
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    invitation_url = preview_data["invitationUrl"]

    # Then approve with the invitation URL
    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": registered_email, "invitationUrl": invitation_url},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Emulates user accepting invitation link
    new_user = await _auth_service.create_user(
        client.app,
        email=registered_email,
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )
    assert new_user["status"] == UserStatus.ACTIVE

    # 3. Test filtering by status
    # a. Check PENDING filter (should exclude the registered user)
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    pending_page = Page[UserAccountGet].model_validate(response_json)

    # The registered user should no longer be in pending status
    pending_emails = [user.email for user in pending_page.data]
    assert registered_email not in pending_emails
    assert len(pending_emails) >= len(pre_registered_users) - 1

    # b. Check REVIEWED users (should include the registered user)
    resp = await client.get(f"{url}?review_status=REVIEWED", headers={X_PRODUCT_NAME_HEADER: product_name})
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    reviewed_page = Page[UserAccountGet].model_validate(response_json)

    # Find the registered user in the reviewed users
    active_user = next(
        (user for user in reviewed_page.data if user.email == registered_email),
        None,
    )
    assert active_user is not None
    assert active_user.account_request_status == "APPROVED"
    assert active_user.status == UserStatus.ACTIVE

    # 4. Test pagination
    # a. First page (limit 2)
    resp = await client.get(
        f"{url}",
        params={"limit": 2, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    page1 = Page[UserAccountGet].model_validate(response_json)

    assert len(page1.data) == 2
    assert page1.meta.limit == 2
    assert page1.meta.offset == 0
    assert page1.meta.total >= len(pre_registered_users)

    # b. Second page (limit 2)
    resp = await client.get(
        f"{url}",
        params={"limit": 2, "offset": 2},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    page2 = Page[UserAccountGet].model_validate(response_json)

    assert len(page2.data) == 2
    assert page2.meta.limit == 2
    assert page2.meta.offset == 2

    # Ensure page 1 and page 2 contain different items
    page1_emails = [user.email for user in page1.data]
    page2_emails = [user.email for user in page2.data]
    assert not set(page1_emails).intersection(page2_emails)

    # 5. Combine status filter with pagination
    resp = await client.get(
        f"{url}",
        params={"review_status": "PENDING", "limit": 2, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    filtered_page = Page[UserAccountGet].model_validate(response_json)

    assert len(filtered_page.data) <= 2
    for user in filtered_page.data:
        assert user.registered is False  # Pending users are not registered
        assert user.account_request_status == "PENDING"


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
@pytest.mark.parametrize(
    "params,expected_email_key,expected_registered,expected_review_statuses",
    [
        (
            {"review_status": "PENDING", "registered": "true", "limit": 50, "offset": 0},
            "pending_registered",
            True,
            {"PENDING"},
        ),
        (
            {"review_status": "PENDING", "registered": "false", "limit": 50, "offset": 0},
            "pending_unregistered",
            False,
            {"PENDING"},
        ),
        (
            {"review_status": "REVIEWED", "registered": "true", "limit": 50, "offset": 0},
            "reviewed_registered",
            True,
            {"APPROVED", "REJECTED"},
        ),
        (
            {"review_status": "REVIEWED", "registered": "false", "limit": 50, "offset": 0},
            "reviewed_unregistered",
            False,
            {"APPROVED", "REJECTED"},
        ),
    ],
    ids=[
        "pending-registered",
        "pending-unregistered",
        "reviewed-registered",
        "reviewed-unregistered",
    ],
)
async def test_list_users_accounts_with_review_status_and_registered_filters(
    client: TestClient,
    user_role,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    seeded_user_accounts_for_registered_review_filters: SeededUserAccountsEmails,
    params: UserAccountsListQueryParams,
    expected_email_key: str,
    expected_registered: bool,
    expected_review_statuses: set[str],
):
    assert client.app

    list_url = client.app.router["list_users_accounts"].url_for()
    query_params: dict[str, str | int] = {
        "review_status": params["review_status"],
        "registered": params["registered"],
        "limit": params["limit"],
        "offset": params["offset"],
    }
    expected_emails = {seeded_user_accounts_for_registered_review_filters[expected_email_key]}
    resp = await client.get(
        f"{list_url}",
        params=query_params,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    payload = await resp.json()
    page = Page[UserAccountGet].model_validate(payload)

    returned_emails = {u.email for u in page.data}
    assert expected_emails.issubset(returned_emails)
    assert all(u.registered is expected_registered for u in page.data)
    assert all(u.account_request_status in expected_review_statuses for u in page.data)

    # The total count must come from the filtered DB result, not from page length.
    total_with_large_page = page.meta.total
    resp = await client.get(
        f"{list_url}",
        params={**query_params, "limit": 1, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    paged_payload = await resp.json()
    paged = Page[UserAccountGet].model_validate(paged_payload)
    assert paged.meta.total == total_with_large_page


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER])
async def test_list_users_accounts_unknown_product_override_returns_409(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    """Passing an unknown product_name query override must yield 409 Conflict, not 404."""
    assert client.app
    invalid_product_name = "nonexistent-product-xyz"

    url = client.app.router["list_users_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts"

    resp = await client.get(
        f"{url}?product_name={invalid_product_name}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    _, error = await assert_status(resp, status.HTTP_409_CONFLICT)

    error_model = ErrorGet.model_validate(error)
    assert error_model.status == status.HTTP_409_CONFLICT
    assert error_model.message == f"Invalid product '{invalid_product_name}'. The specified product does not exist."


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER])
async def test_list_products_for_user_accounts_marks_current_product(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    assert client.app

    url = client.app.router["list_products_for_user_accounts"].url_for()
    assert url.path == "/v0/admin/products"

    resp = await client.get(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    options = TypeAdapter(list[UserAccountProductOptionGet]).validate_python(data)
    current_options = [option for option in options if option.is_current]

    assert current_options
    assert any(option.name == product_name for option in current_options)
