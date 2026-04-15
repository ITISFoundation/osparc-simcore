# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
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


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.PRODUCT_OWNER


class SeededUserAccountsEmails(TypedDict):
    pending_registered: str
    pending_unregistered: str
    reviewed_registered: str
    reviewed_unregistered: str


class UserAccountsListQueryParams(TypedDict):
    review_status: Literal["PENDING", "REVIEWED"]
    registered: Literal["true", "false"]
    limit: int
    offset: int


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
    pre_register_url = client.app.router["pre_register_user_account"].url_for()
    assert pre_register_url.path == "/v0/admin/user-accounts:pre-register"

    pre_registered_users = []
    for _ in range(5):  # Create 5 pre-registered users
        form_data = account_request_form.copy()
        form_data["firstName"] = faker.first_name()
        form_data["lastName"] = faker.last_name()
        form_data["email"] = faker.email()

        resp = await client.post(
            f"{pre_register_url}",
            json=form_data,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        )
        pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
        pre_registered_users.append(pre_registered_data)

    # Verify all pre-registered users are in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts"
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
    assert preview_url.path == "/v0/admin/user-accounts:preview-approval"
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
    assert url.path == "/v0/admin/user-accounts:approve"
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
    assert url.path == "/v0/admin/user-accounts"
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
    assert list_url.path == "/v0/admin/user-accounts"
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


async def test_list_users_accounts_default_sort_preserved(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    account_request_form: dict[str, Any],
):
    """Verify endpoint without sort params returns results (backwards compatible)."""
    assert client.app

    url = client.app.router["list_users_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts"

    # First, create some pre-registered users to sort
    pre_register_url = client.app.router["pre_register_user_account"].url_for()
    form_data = account_request_form.copy()
    form_data["email"] = "test@example.com"
    resp = await client.post(
        f"{pre_register_url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # Query without order_by parameter - should use default sort
    resp = await client.get(
        f"{url}?limit=50&offset=0",
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    # Should get 200 OK response (test backwards compatibility)
    assert resp.status == status.HTTP_200_OK


async def test_list_users_accounts_sorting_by_multiple_fields(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    account_request_form: dict[str, Any],
    faker: Faker,
):
    """Demonstrate sorting by two different fields: email ascending and name ascending."""
    assert client.app

    # Create pre-registered users
    pre_register_url = client.app.router["pre_register_user_account"].url_for()
    test_users = [
        {"firstName": "Alice", "lastName": "Smith", "email": "aalice@example.com"},
        {"firstName": "Bob", "lastName": "Johnson", "email": "bbob@example.com"},
        {"firstName": "Charlie", "lastName": "Brown", "email": "ccharlie@example.com"},
        {"firstName": "Diana", "lastName": "Adams", "email": "ddiana@example.com"},
    ]

    for user_data in test_users:
        form_data = account_request_form.copy()
        form_data.update(user_data)
        resp = await client.post(f"{pre_register_url}", json=form_data, headers={X_PRODUCT_NAME_HEADER: product_name})
        await assert_status(resp, status.HTTP_200_OK)

    url = client.app.router["list_users_accounts"].url_for()

    # Test 1: Sort by email ascending
    resp = await client.get(
        f"{url}",
        params={"order_by": json.dumps({"field": "email", "direction": "asc"}), "limit": 50, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    page1 = Page[UserAccountGet].model_validate(await resp.json())
    emails_sorted = [u.email for u in page1.data]

    # Test 2: Sort by name ascending
    resp = await client.get(
        f"{url}",
        params={"order_by": json.dumps({"field": "name", "direction": "asc"}), "limit": 50, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    page2 = Page[UserAccountGet].model_validate(await resp.json())
    names_sorted = [(u.first_name, u.last_name) for u in page2.data]

    # Verify both sorting work and produce different results
    assert len(emails_sorted) > 0, "Should have results when sorting by email"
    assert len(names_sorted) > 0, "Should have results when sorting by name"

    test_emails = [u["email"] for u in test_users]
    test_names = [(u["firstName"], u["lastName"]) for u in test_users]

    # Get our test users from both results
    result_emails = [e for e in emails_sorted if e in test_emails]
    result_names = [n for n in names_sorted if n in test_names]

    # Verify the sorting order - emails should be sorted
    assert result_emails == sorted(test_emails), f"Emails sorting failed: {result_emails} != {sorted(test_emails)}"
    # Names (by firstName) should also be sorted
    assert result_names == sorted(test_names), f"Names sorting failed: {result_names} != {sorted(test_names)}"
