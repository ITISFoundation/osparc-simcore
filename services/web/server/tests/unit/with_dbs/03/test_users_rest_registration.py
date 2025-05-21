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
import simcore_service_webserver.users
import simcore_service_webserver.users._users_repository
import simcore_service_webserver.users._users_service
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
    product_name: ProductName,
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
            "/v0/admin/users:pre-register",
            json=form_data,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        )
        pre_registered_data, _ = await assert_status(resp, status.HTTP_200_OK)
        pre_registered_users.append(pre_registered_data)

    # Verify all pre-registered users are in PENDING status
    url = client.app.router["list_users_for_admin"].url_for()
    resp = await client.get(
        f"{url}?status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    pending_emails = [user["email"] for user in data if user["status"] is None]
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
    url = client.app.router["list_users_for_admin"].url_for()
    resp = await client.get(
        f"{url}?status=PENDING", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    pending_data, _ = await assert_status(resp, status.HTTP_200_OK)

    # The registered user should no longer be in pending status
    pending_emails = [user["email"] for user in pending_data]
    assert registered_email not in pending_emails
    assert len(pending_emails) >= len(pre_registered_users) - 1

    # b. Check all users
    resp = await client.get(
        f"{url}?status=APPROVED", headers={X_PRODUCT_NAME_HEADER: product_name}
    )
    approved_data, _ = await assert_status(resp, status.HTTP_200_OK)

    # Find the registered user in the active users
    active_user = next(
        (item for item in approved_data if item["email"] == registered_email),
        None,
    )
    assert active_user is not None
    assert UserForAdminGet(**active_user).status == UserStatus.ACTIVE

    # 4. Test pagination
    # a. First page (limit 2)
    resp = await client.get(
        f"{url}",
        params={"limit": 2, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    page1_payload = await resp.json()

    assert len(page1_payload["items"]) == 2
    assert page1_payload["meta"]["limit"] == 2
    assert page1_payload["meta"]["offset"] == 0
    assert page1_payload["meta"]["total"] >= len(pre_registered_users)

    # b. Second page (limit 2)
    resp = await client.get(
        f"{url}",
        params={"limit": 2, "offset": 2},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    assert resp.status == status.HTTP_200_OK
    page2_payload = await resp.json()

    assert len(page2_payload["items"]) == 2
    assert page2_payload["meta"]["limit"] == 2
    assert page2_payload["meta"]["offset"] == 2

    # Ensure page 1 and page 2 contain different items
    page1_emails = [item["email"] for item in page1_payload["data"]]
    page2_emails = [item["email"] for item in page2_payload["data"]]
    assert not set(page1_emails).intersection(page2_emails)

    # 5. Combine status filter with pagination
    resp = await client.get(
        f"{url}",
        params={"status": "PENDING", "limit": 2, "offset": 0},
        headers={X_PRODUCT_NAME_HEADER: product_name},
    )
    filtered_page_data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert len(filtered_page_data) <= 2
    for item in filtered_page_data:
        user = UserForAdminGet(**item)
        assert user.registered is False  # Pending users are not registered
