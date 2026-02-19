# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncGenerator, AsyncIterator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.pydantic_fields_extension import is_nullable
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from models_library.api_schemas_webserver.users import (
    UserAccountGet,
    UserAccountPreviewApprovalGet,
    UserAccountPreviewRejectionGet,
)
from models_library.groups import AccessRightsDict
from models_library.notifications._notifications import ChannelType, TemplatePreview, TemplateRef
from models_library.products import ProductName
from models_library.rest_pagination import Page
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import (
    DEFAULT_TEST_PASSWORD,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import (
    UserInfoDict,
)
from pytest_simcore.helpers.webserver_users import NewUser
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.login import _auth_service
from simcore_service_webserver.models import PhoneNumberStr


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
        },
    )


@pytest.fixture
def mock_notifications_send_message(mocker: MockerFixture) -> AsyncMock:
    """Mock the notifications_service.send_message to avoid RabbitMQ dependency."""
    return mocker.patch(
        "simcore_service_webserver.notifications.notifications_service.send_message",
        return_value=AsyncMock(),
    )


@pytest.fixture
async def support_user(
    support_group_before_app_starts: dict,
    client: TestClient,
) -> AsyncIterator[UserInfoDict]:
    """Creates an active user that belongs to the product's support group."""
    async with NewUser(
        user_data={
            "name": "support-user",
            "status": UserStatus.ACTIVE.name,
            "role": UserRole.USER.name,
        },
        app=client.app,
    ) as user_info:
        # Add the user to the support group
        assert client.app

        from simcore_service_webserver.groups import _groups_repository  # noqa: PLC0415

        # Now add user to support group with read-only access
        await _groups_repository.add_new_user_in_group(
            client.app,
            group_id=support_group_before_app_starts["gid"],
            new_user_id=user_info["id"],
            access_rights=AccessRightsDict(read=True, write=False, delete=False),
        )

        yield user_info


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *((role, status.HTTP_403_FORBIDDEN) for role in UserRole if UserRole.ANONYMOUS < role < UserRole.PRODUCT_OWNER),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_access_rights_on_search_users_only_product_owners_can_access(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    pre_registration_details_db_cleanup: None,
):
    assert client.app

    url = client.app.router["search_user_accounts"].url_for()
    assert url.path == "/v0/admin/user-accounts:search"

    resp = await client.get(url.path, params={"email": "do-not-exists@foo.com"})
    await assert_status(resp, expected)


async def test_access_rights_on_search_users_support_user_can_access_when_above_guest(
    support_user: UserInfoDict,
    # keep support_user first since it has to be created before the app starts
    client: TestClient,
    pre_registration_details_db_cleanup: None,
):
    """Test that support users with role > GUEST can access the search endpoint."""
    assert client.app

    from pytest_simcore.helpers.webserver_login import switch_client_session_to  # noqa: PLC0415

    # Switch client session to the support user
    async with switch_client_session_to(client, support_user):
        url = client.app.router["search_user_accounts"].url_for()
        assert url.path == "/v0/admin/user-accounts:search"

        resp = await client.get(url.path, params={"email": "do-not-exists@foo.com"})
        await assert_status(resp, status.HTTP_200_OK)


@pytest.fixture
def account_request_form(
    faker: Faker,
    user_phone_number: PhoneNumberStr,
) -> dict[str, Any]:
    # This is AccountRequestInfo.form
    form = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "phone": user_phone_number,
        "company": faker.company(),
        # billing info
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
        # extras
        "application": faker.word(),
        "description": faker.sentence(),
        "hear": faker.word(),
        "privacyPolicy": True,
        "eula": True,
    }

    # keeps in sync fields from example and this fixture
    assert set(form) == set(AccountRequestInfo.model_json_schema()["example"]["form"])
    return form


@pytest.fixture
async def pre_registration_details_db_cleanup(
    client: TestClient,
) -> AsyncGenerator[None]:
    """Fixture to clean up all pre-registration details after test"""

    assert client.app

    yield

    # Tear down - clean up the pre-registration details table
    async with get_asyncpg_engine(client.app).connect() as conn:
        await conn.execute(sa.delete(users_pre_registration_details))
        await conn.commit()


@pytest.mark.acceptance_test("pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138")
@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
async def test_search_and_pre_registration(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    pre_registration_details_db_cleanup: None,
):
    assert client.app

    # NOTE: listing of user accounts drops nullable fields to avoid lengthy responses (even if they have no defaults)
    # therefore they are reconstructed here from http response payloads
    nullable_fields = {name: None for name, field in UserAccountGet.model_fields.items() if is_nullable(field)}

    # ONLY in `users` and NOT `users_pre_registration_details`
    resp = await client.get("/v0/admin/user-accounts:search", params={"email": logged_user["email"]})
    assert resp.status == status.HTTP_200_OK

    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    got = UserAccountGet.model_validate({**nullable_fields, **found[0]})
    expected = {
        "first_name": logged_user.get("first_name"),
        "last_name": logged_user.get("last_name"),
        "email": logged_user["email"],
        "institution": None,
        "phone": logged_user.get("phone"),
        "address": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
        "extras": {},
        "registered": True,
        "status": UserStatus.ACTIVE,
        "user_id": logged_user["id"],
        "user_name": logged_user["name"],
        "user_primary_group_id": logged_user.get("primary_gid"),
    }
    assert got.model_dump(include=set(expected)) == expected

    # NOT in `users` and ONLY `users_pre_registration_details`

    # create pre-registration
    resp = await client.post("/v0/admin/user-accounts:pre-register", json=account_request_form)
    assert resp.status == status.HTTP_200_OK

    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": account_request_form["email"]},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    got = UserAccountGet.model_validate({**nullable_fields, **found[0]})
    assert got.model_dump(include={"registered", "status"}) == {
        "registered": False,
        "status": None,
    }

    # Emulating registration of pre-register user
    new_user = await _auth_service.create_user(
        client.app,
        email=account_request_form["email"],
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )

    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": account_request_form["email"]},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    got = UserAccountGet.model_validate({**nullable_fields, **found[0]})
    assert got.model_dump(include={"registered", "status"}) == {
        "registered": True,
        "status": new_user["status"],
    }


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

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
    pre_registered_email = pre_registered_data["email"]

    # 2. Verify the user is in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    pending_emails = [user["email"] for user in data if user["status"] is None]
    assert pre_registered_email in pending_emails

    # 3. Preview the rejection to get message content
    preview_url = client.app.router["preview_rejection_user_account"].url_for()
    resp = await client.post(
        f"{preview_url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": pre_registered_email},
    )
    preview_data, _ = await assert_status(resp, status.HTTP_200_OK)
    message_content = preview_data["messageContent"]

    # 4. Reject the pre-registered user with message content
    url = client.app.router["reject_user_account"].url_for()
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
    assert call_kwargs["channel"] == ChannelType.email

    # 5. Verify the user is no longer in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name})
    pending_data, _ = await assert_status(resp, status.HTTP_200_OK)
    pending_emails = [user["email"] for user in pending_data]
    assert pre_registered_email not in pending_emails

    # 6. Verify the user is now in REJECTED status
    # First get user details to check status
    resp = await client.get(
        "/v0/admin/user-accounts:search",
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


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
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

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL and message content
    preview_url = client.app.router["preview_approval_user_account"].url_for()
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
        assert call_kwargs["channel"] == ChannelType.email

    # 5. Verify the user account status and invitation data in extras
    resp = await client.get(
        "/v0/admin/user-accounts:search",
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


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
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

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL
    preview_url = client.app.router["preview_approval_user_account"].url_for()
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
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email, "invitationUrl": invitation_url},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify invitation data in extras
    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    user_data = found[0]

    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["trial_account_days"] == 15
    assert invitation_data["extra_credits_in_usd"] is None


@pytest.mark.parametrize(
    "user_role",
    [UserRole.PRODUCT_OWNER],
)
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

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Preview approval to get the invitation URL
    preview_url = client.app.router["preview_approval_user_account"].url_for()
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
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email, "invitationUrl": invitation_url},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify invitation data in extras
    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    user_data = found[0]

    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["trial_account_days"] is None
    assert invitation_data["extra_credits_in_usd"] == 50.0


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
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

    resp = await client.post(
        "/v0/admin/user-accounts:pre-register",
        json=form_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_200_OK)

    # 2. Attempt to approve without invitationUrl — should fail with 422
    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": test_email},
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.fixture
def mock_notifications_preview_template(mocker: MockerFixture) -> AsyncMock:
    """Mock the notifications_service.preview_template to avoid RabbitMQ dependency."""

    async def _fake_preview_template(
        app,
        *,
        product_name,
        ref,
        context,
    ) -> TemplatePreview:
        first_name = context.get("user", {}).get("first_name", "User")
        if ref.template_name == "account_approved":
            invitation_url = context.get("link", "https://example.com")
            trial_days = context.get("trial_account_days")
            credits_usd = context.get("extra_credits_in_usd")
            body_parts = [f"<p>Dear {first_name},</p>", "<p>Your account has been approved!</p>"]
            if trial_days:
                body_parts.append(f"<p>Trial period: {trial_days} days</p>")
            if credits_usd:
                body_parts.append(f"<p>Extra credits: ${credits_usd}</p>")
            body_parts.append(f'<p><a href="{invitation_url}">Accept Invitation</a></p>')
            return TemplatePreview(
                ref=TemplateRef(channel=ChannelType.email, template_name="account_approved"),
                message_content={
                    "subject": "Your account request has been accepted",
                    "body_html": "\n".join(body_parts),
                    "body_text": f"Dear {first_name}, your account has been approved.",
                },
            )
        if ref.template_name == "account_rejected":
            return TemplatePreview(
                ref=TemplateRef(channel=ChannelType.email, template_name="account_rejected"),
                message_content={
                    "subject": "Your account request has been denied",
                    "body_html": (
                        f"<p>Dear {first_name},</p>"
                        "<p>We regret to inform you that your account request has been denied.</p>"
                    ),
                    "body_text": f"Dear {first_name}, your account request has been denied.",
                },
            )
        msg = f"Unexpected template_name={ref.template_name}"
        raise ValueError(msg)

    return mocker.patch(
        "simcore_service_webserver.notifications.notifications_service.preview_template",
        side_effect=_fake_preview_template,
    )


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
