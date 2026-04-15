# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.notifications import Channel
from models_library.products import ProductName
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.db.plugin import get_asyncpg_engine


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.PRODUCT_OWNER


async def test_reject_user_account(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_notifications_send_message: AsyncMock,
    mock_notifications_preview_template: AsyncMock,
):
    assert client.app

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = "some-reject-user@email.com"

    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
    pre_registered_email = pre_registered_data["email"]

    # 2. Verify the user is in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts"
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    pending_emails = [user["email"] for user in data if user["status"] is None]
    assert pre_registered_email in pending_emails

    # 3. Preview the rejection to get message content
    preview_url = client.app.router["preview_rejection_user_account"].url_for()
    assert preview_url.path == "/v0/admin/user-accounts:preview-rejection"
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": pre_registered_email},
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    message_content = preview_data["messageContent"]

    # 4. Reject the pre-registered user with message content
    url = client.app.router["reject_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:reject"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": pre_registered_email,
            "messageContent": message_content,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 5. Verify notification was sent
    mock_notifications_send_message.assert_called_once()
    call_kwargs = mock_notifications_send_message.call_args.kwargs
    assert call_kwargs["product_name"] == product_name
    assert call_kwargs["channel"] == Channel.email

    # 5. Verify the user is no longer in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts"
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    pending_data, _ = await assert_status(resp, status.HTTP_200_OK)
    pending_emails = [user["email"] for user in pending_data]
    assert pre_registered_email not in pending_emails

    # 6. Verify the user is now in REJECTED status
    # First get user details to check status
    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"
    resp = await client.get(
        f"{url}",
        params={"email": pre_registered_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    # Check that account_request_status is REJECTED
    user_data = found[0]
    assert user_data["accountRequestStatus"] == "REJECTED"
    assert user_data["accountRequestReviewedBy"] == logged_user["name"]
    assert user_data["accountRequestReviewedAt"] is not None

    # 7. Verify that a rejected user cannot be approved
    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": pre_registered_email,
            "invitationUrl": "https://osparc-simcore.test/#/registration?invitation=fake",
        },
    )
    # Should fail as the account is already reviewed
    assert resp.status == status.HTTP_400_BAD_REQUEST


async def test_approve_user_account_with_full_invitation_details(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_send_message: AsyncMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test approving user account with complete invitation details (trial days + credits)"""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL and message content
    preview_url = client.app.router["preview_approval_user_account"].url_for()
    assert preview_url.path == "/v0/admin/user-accounts:preview-approval"
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": test_email,
            "invitation": {
                "trialAccountDays": 30,
                "extraCreditsInUsd": 100.0,
            },
        },
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    invitation_url = preview_data["invitationUrl"]
    message_content = preview_data.get("messageContent")

    # 3. Approve the user with the invitation URL and message content
    approve_payload: dict[str, Any] = {
        "email": test_email,
        "invitationUrl": invitation_url,
    }
    if message_content:
        approve_payload["messageContent"] = message_content

    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=approve_payload,
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 4. Verify notification was sent if message_content was provided
    if message_content:
        mock_notifications_send_message.assert_called_once()
        call_kwargs = mock_notifications_send_message.call_args.kwargs
        assert call_kwargs["product_name"] == product_name
        assert call_kwargs["channel"] == Channel.email

    # 5. Verify the user account status and invitation data in extras
    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"
    resp = await client.get(
        f"{url}",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    user_data = found[0]
    assert user_data["accountRequestStatus"] == "APPROVED"
    assert user_data["accountRequestReviewedBy"] == logged_user["name"]
    assert user_data["accountRequestReviewedAt"] is not None

    # 5. Verify invitation data is stored in extras
    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["guest"] == test_email
    assert invitation_data["issuer"] == str(logged_user["id"])
    assert invitation_data["trial_account_days"] == 30
    assert invitation_data["extra_credits_in_usd"] == 100.0
    assert invitation_data["product"] == product_name


async def test_approve_user_account_with_trial_days_only(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test approving user account with only trial days"""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL
    preview_url = client.app.router["preview_approval_user_account"].url_for()
    assert preview_url.path == "/v0/admin/user-accounts:preview-approval"
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": test_email,
            "invitation": {"trialAccountDays": 15},
        },
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    invitation_url = preview_data["invitationUrl"]

    # 3. Approve the user with the invitation URL
    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email, "invitationUrl": invitation_url},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify invitation data in extras
    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"
    resp = await client.get(
        f"{url}",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    user_data = found[0]

    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["trial_account_days"] == 15
    assert invitation_data["extra_credits_in_usd"] is None


async def test_approve_user_account_with_credits_only(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
):
    """Test approving user account with only extra credits"""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL
    preview_url = client.app.router["preview_approval_user_account"].url_for()
    assert preview_url.path == "/v0/admin/user-accounts:preview-approval"
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": test_email,
            "invitation": {"extraCreditsInUsd": 50.0},
        },
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    invitation_url = preview_data["invitationUrl"]

    # 3. Approve the user with the invitation URL
    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email, "invitationUrl": invitation_url},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify invitation data in extras
    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"
    resp = await client.get(
        f"{url}",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    user_data = found[0]

    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["trial_account_days"] is None
    assert invitation_data["extra_credits_in_usd"] == 50.0


async def test_approve_user_account_without_invitation_url_fails(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    """Test approving user account without invitationUrl is rejected (field required)"""
    assert client.app

    test_email = faker.email()

    # 1. Create a pre-registered user
    form_data = account_request_form.copy()
    form_data["firstName"] = faker.first_name()
    form_data["lastName"] = faker.last_name()
    form_data["email"] = test_email

    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Attempt to approve without invitationUrl — should fail with 422
    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email},
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def test_create_user_auto_approves_pre_registration_with_recovery_metadata(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    """Test that link_and_update_user_from_pre_registration auto-reconciles PENDING
    pre-registrations when the user has product access, and writes recovery metadata
    into extras.

    SETUP:
    - Pre-register a user via API (PENDING, with form extras)
    - Create a new user with that email
    - Add user to the product group
    - Call link_and_update_user_from_pre_registration

    EXPECTED:
    - Pre-registration status -> APPROVED
    - user_id linked
    - extras.recovery has source, confidence, executed_at, notes
    - Original form extras preserved
    """
    assert client.app

    test_email = account_request_form["email"]

    # 1. Pre-register via API -> creates PENDING record with form extras
    url = client.app.router["pre_register_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:pre-register"
    resp = await client.post(
        f"{url}",
        json=account_request_form,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    pre_reg_data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert pre_reg_data["email"] == test_email

    # 2. Create user + add to product group + link pre-registration
    # (simulating the real registration flow order: create user, add to group, then link)
    from simcore_postgres_database.utils_users import UsersRepo  # noqa: PLC0415

    engine = get_asyncpg_engine(client.app)
    repo = UsersRepo(engine)

    from simcore_service_webserver.security import security_service  # noqa: PLC0415

    new_user = await repo.new_user(
        email=test_email,
        password_hash=security_service.encrypt_password(DEFAULT_TEST_PASSWORD),
        status=UserStatus.ACTIVE,
        expires_at=None,
    )

    # Add user to product group (before link_and_update so reconciliation can trigger)
    from simcore_service_webserver.groups import _groups_repository  # noqa: PLC0415

    await _groups_repository.auto_add_user_to_product_group(
        client.app,
        user_id=new_user.id,
        product_name=product_name,
    )

    # 3. Link and reconcile
    await repo.link_and_update_user_from_pre_registration(
        new_user_id=new_user.id,
        new_user_email=new_user.email,
    )

    # 4. Verify via API
    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"
    resp = await client.get(
        f"{url}",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    user_data = found[0]
    assert user_data["accountRequestStatus"] == "APPROVED"
    assert user_data["registered"] is True

    # 5. Verify recovery metadata in extras
    extras = user_data.get("extras", {})
    assert "recovery" in extras, f"Expected 'recovery' key in extras, got: {extras}"
    recovery = extras["recovery"]
    assert recovery["source"] == "runtime:link_and_update_user_from_pre_registration"
    assert recovery["confidence"] in ("high", "medium")
    assert recovery["executed_at"] is not None
    assert "auto-reconciled" in recovery["notes"].lower()

    # 6. Verify original form extras are preserved (not overwritten)
    assert "application" in extras or "description" in extras or "privacyPolicy" in extras
