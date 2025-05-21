# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from http import HTTPStatus
from typing import Any

import pytest
import simcore_service_webserver.login._auth_service
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from models_library.api_schemas_webserver.users import (
    UserForAdminGet,
)
from models_library.products import ProductName
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import (
    DEFAULT_TEST_PASSWORD,
)
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import (
    UserInfoDict,
)
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER


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
):
    assert client.app

    url = client.app.router["search_users_for_admin"].url_for()
    assert url.path == "/v0/admin/users:search"

    resp = await client.get(url.path, params={"email": "do-not-exists@foo.com"})
    await assert_status(resp, expected)


@pytest.fixture
def account_request_form(faker: Faker) -> dict[str, Any]:
    # This is AccountRequestInfo.form
    form = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "phone": faker.phone_number(),
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
):
    assert client.app

    # ONLY in `users` and NOT `users_pre_registration_details`
    resp = await client.get(
        "/v0/admin/users:search", params={"email": logged_user["email"]}
    )
    assert resp.status == status.HTTP_200_OK

    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserForAdminGet(
        **found[0],
        institution=None,
        address=None,
        city=None,
        state=None,
        postal_code=None,
        country=None,
    )
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
    resp = await client.post("/v0/admin/users:pre-register", json=account_request_form)
    assert resp.status == status.HTTP_200_OK

    resp = await client.get(
        "/v0/admin/users:search", params={"email": account_request_form["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserForAdminGet(**found[0], state=None, status=None)

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
        "/v0/admin/users:search", params={"email": account_request_form["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserForAdminGet(**found[0], state=None)
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
async def test_list_users_for_admin(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
):
    assert client.app

    # Create some pre-registered users
    pre_registered_users = []
    for _ in range(3):
        form_data = account_request_form.copy()
        form_data["firstName"] = faker.first_name()
        form_data["lastName"] = faker.last_name()
        form_data["email"] = faker.email()

        resp = await client.post("/v0/admin/users:pre-register", json=form_data)
        pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
        pre_registered_users.append(pre_registered_data)

    # Register one of the pre-registered users
    new_user = await simcore_service_webserver.login._auth_service.create_user(
        client.app,
        email=pre_registered_users[0]["email"],
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )

    # Test pagination (page 1, limit 2)
    url = client.app.router["list_users_for_admin"].url_for()
    resp = await client.get(f"{url}", params={"page": 1, "per_page": 2})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # Verify pagination structure
    assert "items" in data
    assert "pagination" in data
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 2
    assert data["pagination"]["total"] >= 1  # At least the logged user

    # Test pagination (page 2, limit 2)
    resp = await client.get(f"{url}", params={"page": 2, "per_page": 2})
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["pagination"]["page"] == 2

    # Test filtering by approval status (only approved users)
    resp = await client.get(f"{url}", params={"approved": True})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # All items should be registered users with status
    for item in data["items"]:
        user = UserForAdminGet(**item)
        assert user.registered is True
        assert user.status is not None

    # Test filtering by approval status (only non-approved users)
    resp = await client.get(f"{url}", params={"approved": False})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # All items should be non-registered or non-approved users
    assert len(data["items"]) >= 2  # We created at least 2 non-registered users
    for item in data["items"]:
        user = UserForAdminGet(**item)
        assert user.registered is False or user.status != UserStatus.ACTIVE

    # Combine pagination and filtering
    resp = await client.get(
        f"{url}", params={"approved": True, "page": 1, "per_page": 1}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data["items"]) == 1
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 1

    # Verify content of a specific user
    resp = await client.get(f"{url}", params={"approved": True})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # Find the newly registered user in the list
    registered_user = next(
        (item for item in data["items"] if item["email"] == new_user["email"]),
        None,
    )
    assert registered_user is not None

    user = UserForAdminGet(**registered_user)
    assert user.registered is True
    assert user.status == UserStatus.ACTIVE
    assert user.email == new_user["email"]


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER])
async def test_pending_users_management(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
):
    """Test the management of pending users:
    - list pending users
    - approve user account
    - reject user account
    - resend confirmation email
    """
    assert client.app

    # Create some pre-registered users
    pre_registered_users = []
    for _ in range(3):
        form_data = account_request_form.copy()
        form_data["firstName"] = faker.first_name()
        form_data["lastName"] = faker.last_name()
        form_data["email"] = faker.email()

        resp = await client.post(
            "/v0/admin/users:pre-register",
            json=form_data,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        )
        pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
        pre_registered_users.append(pre_registered_data)

    # 1. List pending users (not yet approved)
    url = client.app.router["list_users_for_admin"].url_for()
    resp = await client.get(
        f"{url}?status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # Verify response structure and content
    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) >= 3  # At least our 3 pre-registered users

    # Verify each pre-registered user is in the list
    for pre_user in pre_registered_users:
        found = next(
            (item for item in data["items"] if item["email"] == pre_user["email"]),
            None,
        )
        assert found is not None
        assert found["registered"] is False

    # 2. Approve one of the pre-registered users
    approval_data = {"email": pre_registered_users[0]["email"]}
    resp = await client.post(
        "/v0/admin/users:approve",
        json=approval_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    approved_data, _ = await assert_status(resp, status.HTTP_200_OK)

    # Verify response structure
    assert "invitationLink" in approved_data
    assert approved_data.get("email") == pre_registered_users[0]["email"]

    # Verify the user is no longer in the pending list
    resp = await client.get(
        f"{url}?status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # The approved user should no longer be in the pending list
    assert all(
        item["email"] != pre_registered_users[0]["email"] for item in data["items"]
    )

    # 3. Reject another pre-registered user
    rejection_data = {"email": pre_registered_users[1]["email"]}
    resp = await client.post(
        "/v0/admin/users:reject",
        json=rejection_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Verify the rejected user is no longer in the pending list
    resp = await client.get(
        f"{url}?status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert all(
        item["email"] != pre_registered_users[1]["email"] for item in data["items"]
    )

    # 4. Resend confirmation email to the approved user
    resend_data = {"email": pre_registered_users[0]["email"]}
    resp = await client.post(
        "/v0/admin/users:resendConfirmationEmail",
        json=resend_data,
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Search for the approved user to confirm their status
    resp = await client.get(
        "/v0/admin/users:search",
        params={"email": pre_registered_users[0]["email"]},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    found_users, _ = await assert_status(resp, status.HTTP_200_OK)

    # Should find exactly one user
    assert len(found_users) == 1
    found_user = UserForAdminGet(**found_users[0])

    # User should be registered but in CONFIRMATION_PENDING status
    assert found_user.registered is True
    assert found_user.status == UserStatus.CONFIRMATION_PENDING
