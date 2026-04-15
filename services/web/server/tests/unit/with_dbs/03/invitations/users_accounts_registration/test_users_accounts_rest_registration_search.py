# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from http import HTTPStatus
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.pydantic_fields_extension import is_nullable
from common_library.users_enums import UserRole, UserStatus
from models_library.api_schemas_webserver.users import UserAccountGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.login import _auth_service


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
