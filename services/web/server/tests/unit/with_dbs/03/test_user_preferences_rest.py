# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any

import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.user_preferences import FrontendUserPreference, PreferenceIdentifier
from models_library.users import UserID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_service_webserver.user_preferences._models import (
    ALL_FRONTEND_PREFERENCES,
)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_GARBAGE_COLLECTOR": "null"}
    )


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
async def user_id(client: TestClient, faker: Faker) -> AsyncIterator[UserID]:
    async with NewUser(
        {"email": faker.email(), "status": UserStatus.ACTIVE.name},
        client.app,
    ) as user:
        yield user["id"]


async def _request_set_frontend_preference(
    client: TestClient, preference_identifier: PreferenceIdentifier, value: Any
) -> ClientResponse:
    assert client.app
    url = f"{client.app.router['set_frontend_preference'].url_for(preference_id=preference_identifier)}"
    assert f"{url}" == f"/v0/me/preferences/{preference_identifier}"
    return await client.patch(url, json={"value": value})


@pytest.mark.parametrize(
    "user_role, expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_204_NO_CONTENT),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_set_frontend_preference_expected_access_rights_response(
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
    user_role: UserRole,
    drop_all_preferences: None,
):
    frontend_preference = ALL_FRONTEND_PREFERENCES[0]()
    resp = await _request_set_frontend_preference(
        client,
        frontend_preference.preference_identifier,
        frontend_preference.get_default_value(),
    )
    await assert_status(resp, expected)


@pytest.fixture(params=ALL_FRONTEND_PREFERENCES)
def frontend_preference(request: pytest.FixtureRequest) -> FrontendUserPreference:
    return request.param()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_set_frontend_preference(
    logged_user: UserInfoDict,
    client: TestClient,
    frontend_preference: FrontendUserPreference,
    user_role: UserRole,
    drop_all_preferences: None,
):
    resp = await _request_set_frontend_preference(
        client,
        frontend_preference.preference_identifier,
        frontend_preference.get_default_value(),
    )
    data, error = await assert_status(resp, status.HTTP_204_NO_CONTENT)
    assert data is None
    assert error is None


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_set_frontend_preference_not_found(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    drop_all_preferences: None,
):
    resp = await _request_set_frontend_preference(
        client, "__undefined_preference_identifier__", None
    )
    _, error = await assert_status(resp, status.HTTP_404_NOT_FOUND)
    assert "not found" in error["message"]
