# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import pytest
import simcore_service_webserver.login._auth_service
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.pydantic_fields_extension import is_nullable
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from models_library.api_schemas_webserver.users import (
    UserAccountGet,
)
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
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.models import PhoneNumberStr


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
        },
    )


@pytest.fixture
def mock_email_session(mocker: MockerFixture) -> AsyncMock:
    """Mock the email session and capture sent messages"""
    # Create a mock email session
    mock_session = AsyncMock()

    # List to store sent messages
    sent_messages = []

    async def mock_send_message(msg):
        """Mock send_message method to capture messages"""
        sent_messages.append(msg)

    mock_session.send_message = mock_send_message
    mock_session.sent_messages = sent_messages

    # Mock the context manager behavior
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Use mocker to patch the create_email_session function
    mocker.patch(
        "simcore_service_webserver.users._accounts_service.create_email_session",
        return_value=mock_session,
    )

    return mock_session


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *(
            (role, status.HTTP_403_FORBIDDEN)
            for role in UserRole
            if role not in {UserRole.PRODUCT_OWNER, UserRole.ANONYMOUS}
        ),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
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
) -> AsyncGenerator[None, None]:
    """Fixture to clean up all pre-registration details after test"""

    assert client.app

    yield

    # Tear down - clean up the pre-registration details table
    async with get_asyncpg_engine(client.app).connect() as conn:
        await conn.execute(sa.delete(users_pre_registration_details))
        await conn.commit()


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
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

    # ONLY in `users` and NOT `users_pre_registration_details`
    resp = await client.get(
        "/v0/admin/user-accounts:search", params={"email": logged_user["email"]}
    )
    assert resp.status == status.HTTP_200_OK

    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    nullable_fields = {
        name: None
        for name, field in UserAccountGet.model_fields.items()
        if is_nullable(field)
    }

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
    }
    assert got.model_dump(include=set(expected)) == expected

    # NOT in `users` and ONLY `users_pre_registration_details`

    # create pre-registration
    resp = await client.post(
        "/v0/admin/user-accounts:pre-register", json=account_request_form
    )
    assert resp.status == status.HTTP_200_OK

    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": account_request_form["email"]},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserAccountGet(**found[0], state=None, status=None)

    assert got.model_dump(include={"registered", "status"}) == {
        "registered": False,
        "status": None,
    }

    # Emulating registration of pre-register user
    new_user = (
        await simcore_service_webserver.login._auth_service.create_user(  # noqa: SLF001
            client.app,
            email=account_request_form["email"],
            password=DEFAULT_TEST_PASSWORD,
            status_upon_creation=UserStatus.ACTIVE,
            expires_at=None,
        )
    )

    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": account_request_form["email"]},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserAccountGet(**found[0], state=None)
    assert got.model_dump(include={"registered", "status"}) == {
        "registered": True,
        "status": new_user["status"].name,
    }


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
async def test_list_users_accounts(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
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
    resp = await client.get(
        f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()

    # Parse response into Page[UserForAdminGet] model
    page_model = Page[UserAccountGet].model_validate(response_json)

    # Access the items field from the paginated response
    pending_users = [
        user for user in page_model.data if user.account_request_status == "PENDING"
    ]
    pending_emails = [user.email for user in pending_users]

    for pre_user in pre_registered_users:
        assert pre_user["email"] in pending_emails

    # 2. Register one of the pre-registered users: approve + create account
    registered_email = pre_registered_users[0]["email"]

    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": registered_email},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Emulates user accepting invitation link
    new_user = await simcore_service_webserver.login._auth_service.create_user(
        client.app,
        email=registered_email,
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )

    # 3. Test filtering by status
    # a. Check PENDING filter (should exclude the registered user)
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(
        f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    assert resp.status == status.HTTP_200_OK
    response_json = await resp.json()
    pending_page = Page[UserAccountGet].model_validate(response_json)

    # The registered user should no longer be in pending status
    pending_emails = [user.email for user in pending_page.data]
    assert registered_email not in pending_emails
    assert len(pending_emails) >= len(pre_registered_users) - 1

    # b. Check REVIEWED users (should include the registered user)
    resp = await client.get(
        f"{url}?review_status=REVIEWED", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
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
    mock_email_session: AsyncMock,
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
    resp = await client.get(
        f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    pending_emails = [user["email"] for user in data if user["status"] is None]
    assert pre_registered_email in pending_emails

    # 3. Reject the pre-registered user
    url = client.app.router["reject_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": pre_registered_email},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 4. Verify rejection email was sent
    # Wait a bit for fire-and-forget task to complete

    await asyncio.sleep(0.1)

    assert len(mock_email_session.sent_messages) == 1
    rejection_msg = mock_email_session.sent_messages[0]

    # Verify email recipients and content
    assert pre_registered_email in rejection_msg["To"]
    assert "denied" in rejection_msg["Subject"].lower()

    # 5. Verify the user is no longer in PENDING status
    url = client.app.router["list_users_accounts"].url_for()
    resp = await client.get(
        f"{url}?review_status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
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
    assert user_data["accountRequestReviewedBy"] == logged_user["id"]
    assert user_data["accountRequestReviewedAt"] is not None

    # 7. Verify that a rejected user cannot be approved
    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json={"email": pre_registered_email},
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
    mock_email_session: AsyncMock,
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

    # 2. Approve the user with full invitation details
    approval_payload = {
        "email": test_email,
        "invitation": {
            "trialAccountDays": 30,
            "extraCreditsInUsd": 100.0,
        },
    }

    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=approval_payload,
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify approval email was sent
    # Wait a bit for fire-and-forget task to complete

    await asyncio.sleep(0.1)

    assert len(mock_email_session.sent_messages) == 1
    approval_msg = mock_email_session.sent_messages[0]

    # Verify email recipients and content
    assert test_email in approval_msg["To"]
    assert "accepted" in approval_msg["Subject"].lower()

    # 4. Verify the user account status and invitation data in extras
    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    user_data = found[0]
    assert user_data["accountRequestStatus"] == "APPROVED"
    assert user_data["accountRequestReviewedBy"] == logged_user["id"]
    assert user_data["accountRequestReviewedAt"] is not None

    # 5. Verify invitation data is stored in extras
    assert "invitation" in user_data["extras"]
    invitation_data = user_data["extras"]["invitation"]
    assert invitation_data["guest"] == test_email
    assert invitation_data["issuer"] == str(logged_user["id"])
    assert invitation_data["trial_account_days"] == 30
    assert invitation_data["extra_credits_in_usd"] == 100.0
    assert "invitation_url" in invitation_data


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

    # 2. Approve the user with only trial days
    approval_payload = {
        "email": test_email,
        "invitation": {
            "trialAccountDays": 15,
            # No extra_credits_in_usd
        },
    }

    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=approval_payload,
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

    # 2. Approve the user with only extra credits
    approval_payload = {
        "email": test_email,
        "invitation": {
            # No trial_account_days
            "extraCreditsInUsd": 50.0,
        },
    }

    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=approval_payload,
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
async def test_approve_user_account_without_invitation(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    pre_registration_details_db_cleanup: None,
):
    """Test approving user account without any invitation details"""
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

    # 2. Approve the user without invitation
    approval_payload = {
        "email": test_email,
        # No invitation field
    }

    url = client.app.router["approve_user_account"].url_for()
    resp = await client.post(
        f"{url}",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        json=approval_payload,
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # 3. Verify no invitation data in extras
    resp = await client.get(
        "/v0/admin/user-accounts:search",
        params={"email": test_email},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    user_data = found[0]

    assert user_data["accountRequestStatus"] == "APPROVED"
    # Verify no invitation data stored
    assert "invitation" not in user_data["extras"]
