# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any, TypedDict
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.notifications import Channel
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_users import insert_and_get_user_and_secrets_lifespan
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.aiohttp.observer import register_observer
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.products import products_service
from simcore_service_webserver.signals import SIGNAL_ON_USER_CONFIRMATION
from simcore_service_webserver.users import _accounts_service
from simcore_service_webserver.users.schemas import UserAccountRestPreRegister
from simcore_service_webserver.wallets import _api as _wallets_service
from simcore_service_webserver.wallets import _db as _wallets_repository


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.PRODUCT_OWNER


class ExistingRegisteredUser(TypedDict):
    """Structured output of `existing_registered_user`: the inserted `users` row
    (key columns) merged with the `password_hash` of its `users_secrets` row.
    """

    id: int
    name: str
    email: str
    status: str
    role: str
    created: datetime
    expires_at: datetime | None
    password_hash: str


@pytest.fixture
async def existing_registered_user(
    client: TestClient,
    account_request_form: dict[str, Any],
) -> AsyncIterator[ExistingRegisteredUser]:
    """An ACTIVE registered account (`users` + `users_secrets` rows) whose email matches
    `account_request_form["email"]`, so the same email can be pre-registered and later
    approved through the "skip invitation" path. Auto-cleaned after the test.
    """
    assert client.app
    async with insert_and_get_user_and_secrets_lifespan(  # pylint: disable=contextmanager-generator-missing-cleanup
        get_asyncpg_engine(client.app),
        email=account_request_form["email"],
    ) as user_row:
        yield ExistingRegisteredUser(**user_row)


async def test_reject_user_account(  # pylint: disable=too-many-statements
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
    bcc_emails = [faker.email(), faker.email()]
    url = client.app.router["reject_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:reject"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": pre_registered_email,
            "bccEmails": bcc_emails,
            "messageContent": message_content,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 5. Verify notification was sent
    mock_notifications_send_message.assert_called_once()
    call_kwargs = mock_notifications_send_message.call_args.kwargs
    assert call_kwargs["product_name"] == product_name
    assert call_kwargs["channel"] == Channel.email
    # bcc emails from the request are propagated to the notification
    assert [contact.email for contact in call_kwargs["bcc"]] == bcc_emails

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
    bcc_emails = [faker.email(), faker.email()]
    approve_payload: dict[str, Any] = {
        "email": test_email,
        "invitationUrl": invitation_url,
        "bccEmails": bcc_emails,
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
        # bcc emails from the request are propagated to the notification
        assert call_kwargs["bcc"] is not None
        assert [contact.email for contact in call_kwargs["bcc"]] == bcc_emails

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
    """Test approving a NEW (not yet registered) user without invitationUrl is rejected.

    NOTE: invitationUrl is optional at the REST schema level (an already-registered
    user is approved without one, see
    test_approve_user_account_skips_invitation_for_already_registered_user), but it
    is still required by the service to approve a genuinely new user.
    """
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

    # 2. Attempt to approve without invitationUrl — should fail with 400
    url = client.app.router["approve_user_account"].url_for()
    assert url.path == "/v0/admin/user-accounts:approve"
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email},
    )
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)


async def test_create_user_auto_approves_pre_registration_with_recovery_metadata(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    existing_registered_user: ExistingRegisteredUser,
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

    # 2. Add the (already-created, fixture) user to the product group and link the
    # pre-registration (simulating the real registration flow order: create user,
    # add to group, then link)
    from simcore_postgres_database.utils_users import UsersRepo  # noqa: PLC0415

    repo = UsersRepo(get_asyncpg_engine(client.app))

    # Add user to product group (before link_and_update so reconciliation can trigger)
    from simcore_service_webserver.groups import _groups_repository  # noqa: PLC0415

    await _groups_repository.auto_add_user_to_product_group(
        client.app,
        user_id=existing_registered_user["id"],
        product_name=product_name,
    )

    # 3. Link and reconcile
    await repo.link_and_update_user_from_pre_registration(
        new_user_id=existing_registered_user["id"],
        new_user_email=existing_registered_user["email"],
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


async def test_approve_user_account_skips_invitation_for_already_registered_user(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    existing_registered_user: ExistingRegisteredUser,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mock_notifications_send_message: AsyncMock,
    mock_notifications_preview_template: AsyncMock,
    mocker: MockerFixture,
):
    """An already-registered user granted access to a new product must be added
    directly to that product's group, with no invitation generated, and must
    receive the extra credits (in USD) the PO decided on at approval time.

    SEE decision: https://github.com/ITISFoundation/private-issues/issues/461#issuecomment-4981796351
    : invitation-based password redefinition confused users who already had an account.
    """
    assert client.app

    extra_credits_in_usd = 20

    # The default test product has no price (payment disabled), so fake a
    # payment-enabled product (1 credit per USD) to exercise the credits grant
    product = products_service.get_product(client.app, product_name)
    payment_enabled_product = product.model_copy(update={"is_payment_enabled": True, "credits_per_usd": Decimal(1)})
    mocker.patch(
        "simcore_service_webserver.products.products_service.get_product",
        return_value=payment_enabled_product,
    )
    mock_add_credits_to_wallet = mocker.patch(
        "simcore_service_webserver.wallets._events.resource_usage_service.add_credits_to_wallet",
        spec=True,
        return_value=None,
    )

    test_email = account_request_form["email"]

    # 1. A registered (ACTIVE) user with that email exists (fixture), and is
    #    NOT yet a member of `product_name`

    # 2. Admin pre-registers that same email for `product_name` (the user has no access yet)
    url = client.app.router["pre_register_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        json=account_request_form,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 3. Preview approval: no invitation should be generated for a registered user
    preview_url = client.app.router["preview_approval_user_account"].url_for()
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email, "invitation": {}},
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert preview_data.get("invitationUrl") is None
    message_content = preview_data["messageContent"]

    # 4. Approve without an invitationUrl, granting extra credits to the
    # already-registered user (the PO's decision, like in registration)
    resp = await client.post(
        f"{client.app.router['approve_user_account'].url_for()}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={
            "email": test_email,
            "messageContent": message_content,
            "extraCreditsInUsd": extra_credits_in_usd,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 5. The user is now a member of the product, request is APPROVED
    url = client.app.router["search_user_accounts"].url_for()
    resp = await client.get(
        f"{url}",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    user_data = found[0]
    assert user_data["accountRequestStatus"] == "APPROVED"
    assert user_data["userId"] == existing_registered_user["id"]
    assert product_name in user_data["products"]

    # the PO's credits decision is persisted in the pre-registration extras (audit)
    assert user_data["extras"]["approval"] == {"extra_credits_in_usd": extra_credits_in_usd}

    # 6. Notification was sent using the "added to product" template, not "approved"
    mock_notifications_send_message.assert_called_once()

    # 7. The user must get a default wallet in the new product (via
    # SIGNAL_ON_USER_CONFIRMATION emitted on approval), just like on registration.
    wallets = await _wallets_service.list_wallets_for_user(
        client.app, user_id=existing_registered_user["id"], product_name=product_name
    )
    assert len(wallets) == 1

    # 8. and the wallet is topped up with the credits the PO granted
    assert mock_add_credits_to_wallet.called
    credits_kwargs = mock_add_credits_to_wallet.call_args_list[0].kwargs
    assert credits_kwargs["wallet_id"] == wallets[0].wallet_id
    assert credits_kwargs["user_id"] == existing_registered_user["id"]
    assert credits_kwargs["product_name"] == product_name
    assert credits_kwargs["osparc_credits"] == extra_credits_in_usd * payment_enabled_product.credits_per_usd
    assert credits_kwargs["payment_id"] == "INVITATION"

    # delete to allow teardown
    await _wallets_repository.delete_wallet(
        client.app,
        wallet_id=wallets[0].wallet_id,
        product_name=product_name,
    )


async def test_approve_user_account_emits_user_confirmation_signal_for_existing_user(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    existing_registered_user: ExistingRegisteredUser,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
    mocker: MockerFixture,
):
    """Regression test (FogBugz #249452): approving the account request of an
    already-registered user (the "skip invitation" path in
    users/_accounts_service.py::_approve_existing_user) must emit
    SIGNAL_ON_USER_CONFIRMATION, just like the self-registration path
    (login/_controller/rest/registration.py).

    The wallets plugin auto-creates the default wallet and grants the PO's
    extra credits only as an observer of that signal, so forgetting to emit it
    left those users without their welcome credits.
    """
    assert client.app

    # keep the wallets observer out of the way: this test pins the emission of
    # the signal itself (its wallet-creation side effects are covered elsewhere)
    mock_wallet_observer = mocker.patch(
        "simcore_service_webserver.wallets._events._auto_add_default_wallet",
        spec=True,
        return_value=None,
    )

    # 1. An existing ACTIVE account (e.g. registered in another product) — fixture
    existing_email = account_request_form["email"]
    assert existing_registered_user["email"] == existing_email

    # 2. Its PENDING pre-registration for `product_name`, linked to the account
    #    (pre_register_user links an existing user by email, which is what selects
    #    the _approve_existing_user path)
    profile = UserAccountRestPreRegister.model_validate(account_request_form)
    await _accounts_service.pre_register_user(
        client.app,
        profile=profile,
        creator_user_id=logged_user["id"],
        product_name=product_name,
    )

    # 3. Probe observer on the same seam the wallets plugin subscribes to
    signal_calls: list[dict[str, Any]] = []

    async def _probe(**kwargs: Any) -> None:
        signal_calls.append(kwargs)

    register_observer(client.app, _probe, SIGNAL_ON_USER_CONFIRMATION)

    # 4. PO approves the request (no invitation needed for an existing account)
    extra_credits_in_usd = 42
    await _accounts_service.approve_user_account(
        client.app,
        pre_registration_email=existing_email,
        product_name=product_name,
        reviewer_id=logged_user["id"],
        extra_credits_in_usd=extra_credits_in_usd,
    )

    # 5. SIGNAL_ON_USER_CONFIRMATION emitted exactly once with the right payload
    assert signal_calls == [
        {
            "user_id": existing_registered_user["id"],
            "product_name": product_name,
            "extra_credits_in_usd": extra_credits_in_usd,
        }
    ]

    # and the wallets observer (default wallet + credits grant) ran on it
    mock_wallet_observer.assert_awaited_once_with(
        client.app,
        user_id=existing_registered_user["id"],
        product_name=product_name,
        extra_credits_in_usd=extra_credits_in_usd,
    )
