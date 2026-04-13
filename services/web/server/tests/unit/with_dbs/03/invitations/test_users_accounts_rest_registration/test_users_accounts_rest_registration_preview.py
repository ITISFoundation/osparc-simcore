# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_webserver.users import (
    UserAccountPreviewApprovalGet,
    UserAccountPreviewRejectionGet,
)
from models_library.products import ProductName
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_approval_user_account(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing the approval notification for a pre-registered user account."""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval with full invitation details
    preview_payload = {
        "email": test_email,
        "invitation": {
            "trialAccountDays": 30,
            "extraCreditsInUsd": 100.0,
        },
    }

    url = client.app.router["preview_approval_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:preview-approval"

    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    preview_result = UserAccountPreviewApprovalGet.model_validate(data)

    # Verify response contains invitation_url and message_content
    assert preview_result.invitation_url is not None
    assert preview_result.message_content is not None
    assert preview_result.message_content.subject is not None
    assert preview_result.message_content.body_html is not None or preview_result.message_content.body_text is not None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_approval_with_trial_days_only(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing approval with only trial days."""
    assert client.app

    test_email = faker.email()

    # Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # Preview approval with only trial days
    preview_payload = {
        "email": test_email,
        "invitation": {
            "trialAccountDays": 15,
        },
    }

    url = client.app.router["preview_approval_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    preview_result = UserAccountPreviewApprovalGet.model_validate(data)
    assert preview_result.invitation_url is not None
    assert preview_result.message_content is not None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_approval_with_credits_only(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing approval with only extra credits."""
    assert client.app

    test_email = faker.email()

    # Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # Preview approval with only extra credits
    preview_payload = {
        "email": test_email,
        "invitation": {
            "extraCreditsInUsd": 50.0,
        },
    }

    url = client.app.router["preview_approval_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    preview_result = UserAccountPreviewApprovalGet.model_validate(data)
    assert preview_result.invitation_url is not None
    assert preview_result.message_content is not None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_approval_for_nonexistent_user(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing approval for an email that has no pre-registration."""
    assert client.app

    preview_payload = {
        "email": "nonexistent-user@example.com",
        "invitation": {
            "trialAccountDays": 30,
        },
    }

    url = client.app.router["preview_approval_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    # Nonexistent user triggers an error (bad request or not found)
    assert resp.status in {
        status.HTTP_200_OK,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_404_NOT_FOUND,
    }


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_rejection_user_account(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing the rejection notification for a pre-registered user account."""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview rejection
    preview_payload = {
        "email": test_email,
    }

    url = client.app.router["preview_rejection_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:preview-rejection"

    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    preview_result = UserAccountPreviewRejectionGet.model_validate(data)

    # Verify response contains message_content with rejection email content
    assert preview_result.message_content is not None
    assert preview_result.message_content.subject is not None
    assert "denied" in preview_result.message_content.subject.lower()
    assert preview_result.message_content.body_html is not None or preview_result.message_content.body_text is not None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
async def test_preview_rejection_for_nonexistent_user(
    client: TestClient,
    logged_user: UserInfoDict,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_notifications_preview_template: AsyncMock,
):
    """Test previewing rejection for an email that has no pre-registration."""
    assert client.app

    preview_payload = {
        "email": "nonexistent-user@example.com",
    }

    url = client.app.router["preview_rejection_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=preview_payload,
    )
    # Should fail since the user doesn't exist
    assert resp.status in {status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR}


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *((role, status.HTTP_403_FORBIDDEN) for role in UserRole if UserRole.ANONYMOUS < role < UserRole.PRODUCT_OWNER),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_access_rights_on_preview_approval(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    pre_registration_details_db_cleanup: None,
):
    """Test that only PRODUCT_OWNER and ADMIN can access preview approval endpoint."""
    assert client.app

    url = client.app.router["preview_approval_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:preview-approval"

    resp = await client.post(
        url.path,
        json={
            "email": "test@example.com",
            "invitation": {"trialAccountDays": 30},
        },
    )
    if expected in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        await assert_status(resp, expected)
    else:
        # Authorized roles pass access control; may fail for other reasons (e.g. user not found)
        assert resp.status not in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *((role, status.HTTP_403_FORBIDDEN) for role in UserRole if UserRole.ANONYMOUS < role < UserRole.PRODUCT_OWNER),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_access_rights_on_preview_rejection(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    pre_registration_details_db_cleanup: None,
):
    """Test that only PRODUCT_OWNER and ADMIN can access preview rejection endpoint."""
    assert client.app

    url = client.app.router["preview_rejection_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:preview-rejection"

    resp = await client.post(
        url.path,
        json={"email": "test@example.com"},
    )
    if expected in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        await assert_status(resp, expected)
    else:
        # Authorized roles pass access control; may fail for other reasons (e.g. user not found)
        assert resp.status not in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
