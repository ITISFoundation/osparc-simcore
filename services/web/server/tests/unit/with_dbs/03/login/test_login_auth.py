# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography import fernet
from faker import Faker
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.utils_users import UsersRepo
from simcore_service_webserver.application_keys import APP_SETTINGS_APPKEY
from simcore_service_webserver.db.models import UserStatus
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.login import _auth_service
from simcore_service_webserver.login.constants import (
    MSG_ACTIVATION_REQUIRED,
    MSG_INVALID_CREDENTIALS,
    MSG_LOGGED_IN,
    MSG_LOGIN_TOO_MANY_ATTEMPTS,
    MSG_UNKNOWN_EMAIL,
    MSG_USER_BANNED,
    MSG_USER_DELETED,
    MSG_USER_EXPIRED,
)
from simcore_service_webserver.security import security_service
from simcore_service_webserver.session.settings import get_plugin_settings
from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.mark.parametrize("user_role", [role for role in UserRole if role >= UserRole.USER])
async def test_check_auth(client: TestClient, logged_user: UserInfoDict):
    assert client.app

    url = client.app.router["check_auth"].url_for()
    assert url.path == "/v0/auth:check"

    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_204_NO_CONTENT)

    response = await client.post("/v0/auth/logout")
    await assert_status(response, status.HTTP_200_OK)

    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


def test_login_plugin_setup_succeeded(client: TestClient):
    assert client.app
    print(client.app[APP_SETTINGS_APPKEY].model_dump_json(indent=1))

    # this should raise AssertionError if not succeedd
    settings = get_plugin_settings(client.app)
    assert settings


async def test_login_with_unknown_email(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(url.path, json={"email": "unknown@email.com", "password": "wrong."})

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_UNKNOWN_EMAIL not in await r.text()
    assert MSG_INVALID_CREDENTIALS in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


async def test_login_unknown_email_is_indistinguishable_from_wrong_password(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    r_unknown = await client.post(url.path, json={"email": "unknown@email.com", "password": "wrong."})
    async with NewUser(app=client.app) as user:
        r_wrong = await client.post(url.path, json={"email": user["email"], "password": "wrong."})

    assert r_unknown.status == r_wrong.status == status.HTTP_401_UNAUTHORIZED
    _, error_unknown = await assert_status(r_unknown, status.HTTP_401_UNAUTHORIZED)
    _, error_wrong = await assert_status(r_wrong, status.HTTP_401_UNAUTHORIZED)
    assert error_unknown["errors"] == error_wrong["errors"]
    assert error_unknown["message"] == error_wrong["message"]


async def test_login_with_wrong_password(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    r = await client.post(url.path)
    payload = await r.json()

    assert MSG_INVALID_CREDENTIALS not in await r.text(), str(payload)

    async with NewUser(app=client.app) as user:
        r = await client.post(
            url.path,
            json={
                "email": user["email"],
                "password": "wrong.",
            },
        )
    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_INVALID_CREDENTIALS in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


@pytest.mark.parametrize(
    "user_status,expected_msg",
    [
        (UserStatus.BANNED, MSG_USER_BANNED),
        (UserStatus.EXPIRED, MSG_USER_EXPIRED),
        (UserStatus.DELETED, MSG_USER_DELETED),
    ],
)
async def test_login_blocked_user(client: TestClient, user_status: UserStatus, expected_msg: str):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(url.path)
    assert expected_msg not in await r.text()

    async with NewUser({"status": user_status.name}, app=client.app) as user:
        r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    # expected_msg contains {support_email} at the end of the string
    assert expected_msg[: -len("xxx{support_email}")] in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


@pytest.mark.parametrize(
    "user_status",
    [UserStatus.BANNED, UserStatus.EXPIRED, UserStatus.DELETED, UserStatus.CONFIRMATION_PENDING],
)
async def test_login_blocked_user_with_wrong_password_does_not_reveal_status(
    client: TestClient, user_status: UserStatus
):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser({"status": user_status.name}, app=client.app) as user:
        r = await client.post(url.path, json={"email": user["email"], "password": "wrong."})

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert error["errors"][0]["message"] == MSG_INVALID_CREDENTIALS


async def test_login_inactive_user(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(url.path)
    assert MSG_ACTIVATION_REQUIRED not in await r.text()

    async with NewUser({"status": UserStatus.CONFIRMATION_PENDING.name}, app=client.app) as user:
        r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_ACTIVATION_REQUIRED in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


async def test_login_successfully(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser(app=client.app) as user:
        r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})

    data, _ = await assert_status(r, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]


async def test_login_migrates_legacy_password_hash_to_argon2id(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    repo = UsersRepo(get_asyncpg_engine(client.app))

    async with NewUser(app=client.app) as user:
        # NewUser seeds a legacy sha256_crypt hash
        legacy_hash = await repo.get_password_hash(user_id=user["id"])
        assert legacy_hash.startswith("$5$")

        credentials = {"email": user["email"], "password": user["raw_password"]}
        r = await client.post(url.path, json=credentials)
        await assert_status(r, status.HTTP_200_OK)

        migrated_hash = await repo.get_password_hash(user_id=user["id"])
        assert migrated_hash.startswith("$argon2id$")
        assert security_service.check_password(user["raw_password"], migrated_hash)

        # an up-to-date hash is not rewritten on the next login
        r = await client.post(url.path, json=credentials)
        await assert_status(r, status.HTTP_200_OK)
        assert await repo.get_password_hash(user_id=user["id"]) == migrated_hash


async def test_login_with_wrong_password_keeps_legacy_password_hash(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    repo = UsersRepo(get_asyncpg_engine(client.app))

    async with NewUser(app=client.app) as user:
        legacy_hash = await repo.get_password_hash(user_id=user["id"])

        r = await client.post(url.path, json={"email": user["email"], "password": "wrong."})
        await assert_status(r, status.HTTP_401_UNAUTHORIZED)

        assert await repo.get_password_hash(user_id=user["id"]) == legacy_hash


async def test_login_rehash_does_not_overwrite_concurrent_password_change(
    client: TestClient, mocker: MockerFixture, faker: Faker
):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    repo = UsersRepo(get_asyncpg_engine(client.app))
    concurrent_hash = security_service.encrypt_password(faker.password())

    original = UsersRepo.update_user_password_hash_if_unchanged

    async def _password_changed_just_before_update(
        self: UsersRepo,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        expected_password_hash: str,
        new_password_hash: str,
    ) -> bool:
        await self.update_user_password_hash(user_id=user_id, password_hash=concurrent_hash)
        return await original(
            self,
            connection,
            user_id=user_id,
            expected_password_hash=expected_password_hash,
            new_password_hash=new_password_hash,
        )

    mocker.patch.object(UsersRepo, "update_user_password_hash_if_unchanged", _password_changed_just_before_update)

    async with NewUser(app=client.app) as user:
        r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})
        await assert_status(r, status.HTTP_200_OK)

        assert await repo.get_password_hash(user_id=user["id"]) == concurrent_hash


async def test_login_successfully_with_email_containing_uppercase_letters(
    client: TestClient,
    faker: Faker,
):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    # Testing auth with upper case email for user registered with lower case email
    async with NewUser(app=client.app) as user:
        r = await client.post(
            url.path,
            json={
                "email": user["email"].upper(),  # <--- upper case email
                "password": user["raw_password"],
            },
        )
    data, _ = await assert_status(r, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]


@pytest.mark.parametrize(
    "cookie_enabled,expected",
    [(True, status.HTTP_200_OK), (False, status.HTTP_401_UNAUTHORIZED)],
)
async def test_proxy_login(client: TestClient, cookie_enabled: bool, expected: HTTPStatus):
    assert client.app
    restricted_url = client.app.router["get_my_profile"].url_for()
    assert str(restricted_url) == "/v0/me"

    def _build_proxy_session_cookie(identity: str):
        # NOTE: Creates proxy session for authenticated uses in the api-server.
        # Will be used as temporary solution until common authentication
        # service is in place
        #
        assert client.app
        # Based on aiohttp_session and aiohttp_security
        # HACK to get secret for testing purposes  # noqa: FIX004
        session_settings = get_plugin_settings(client.app)
        _fernet = fernet.Fernet(session_settings.SESSION_SECRET_KEY.get_secret_value())

        # builds session cookie
        cookie_name = DEFAULT_SESSION_COOKIE_NAME
        cookie_data = json.dumps(
            {
                "created": int(time.time()),  # now
                "session": {"AIOHTTP_SECURITY": identity},
                "path": "/",
                # extras? e.g. expiration
            }
        ).encode("utf-8")
        encrypted_cookie_data = _fernet.encrypt(cookie_data).decode("utf-8")

        return {cookie_name: encrypted_cookie_data}

    # ---
    async with NewUser(app=client.app) as user:
        cookies = _build_proxy_session_cookie(identity=user["email"]) if cookie_enabled else {}

        resp = await client.get(f"{restricted_url}", cookies=cookies)
        data, error = await assert_status(resp, expected)

        if not error:
            assert data["login"] == user["email"]


@pytest.fixture
async def multiple_users(client: TestClient, num_users: int = 5) -> AsyncIterator[list[dict[str, str]]]:
    """Fixture that creates multiple test users with an AsyncExitStack for cleanup."""
    async with AsyncExitStack() as exit_stack:
        users = []
        for _ in range(num_users):
            # Use enter_async_context to properly register each NewUser context manager
            user_ctx = await exit_stack.enter_async_context(NewUser(app=client.app))
            users.append(
                {
                    "email": user_ctx["email"],
                    "password": user_ctx["raw_password"],
                }
            )

        yield users
        # AsyncExitStack will automatically clean up all users when exiting


async def test_multiple_users_login_logout_concurrently(
    web_server: TestServer,
    client: TestClient,
    multiple_users: list[dict[str, str]],
    aiohttp_client: Callable,
):
    """Test multiple users can login concurrently and properly get logged out."""
    assert client.app

    # URLs
    login_url = client.app.router["auth_login"].url_for().path
    profile_url = client.app.router["get_my_profile"].url_for().path
    logout_url = client.app.router["auth_logout"].url_for().path

    async def user_session_flow(user_creds):
        # Create a new client for each user to ensure isolated sessions
        user_client = await aiohttp_client(web_server)

        # Login
        login_resp = await user_client.post(
            login_url,
            json={"email": user_creds["email"], "password": user_creds["password"]},
        )
        login_data, _ = await assert_status(login_resp, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in login_data["message"]

        # Access profile (cookies are automatically sent by the client)
        profile_resp = await user_client.get(profile_url)
        profile_data, _ = await assert_status(profile_resp, status.HTTP_200_OK)
        assert profile_data["login"] == user_creds["email"]

        # Logout
        logout_resp = await user_client.post(logout_url)
        await assert_status(logout_resp, status.HTTP_200_OK)

        # Try to access profile after logout
        profile_after_logout_resp = await user_client.get(profile_url)
        await assert_status(profile_after_logout_resp, status.HTTP_401_UNAUTHORIZED)

        # No need to manually close the client as aiohttp_client fixture handles cleanup

    await user_session_flow(multiple_users[0])

    # Run all user flows concurrently
    await asyncio.gather(*(user_session_flow(user) for user in multiple_users))


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    # long enough for a slow run not to outlive the back-off between two requests
    return app_environment | setenvs_from_dict(monkeypatch, {"LOGIN_THROTTLE_BASE_DELAY_SEC": "60"})


def _free_failed_login_attempts(client: TestClient) -> int:
    assert client.app
    login_settings = client.app[APP_SETTINGS_APPKEY].WEBSERVER_LOGIN
    assert login_settings
    return login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS


async def test_login_is_throttled_after_repeated_wrong_passwords(client: TestClient, mocker: MockerFixture):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser(app=client.app) as user:
        for _ in range(_free_failed_login_attempts(client) + 1):
            r = await client.post(url.path, json={"email": user["email"], "password": "wrong."})
            await assert_status(r, status.HTTP_401_UNAUTHORIZED)

        check_credentials = mocker.spy(_auth_service, "check_authorized_user_credentials")
        r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})

        _, error = await assert_status(r, status.HTTP_429_TOO_MANY_REQUESTS)
        assert MSG_LOGIN_TOO_MANY_ATTEMPTS in error["message"]
        assert int(r.headers["Retry-After"]) > 0
        check_credentials.assert_not_called()


async def test_login_throttle_is_per_email(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser(app=client.app) as blocked_user, NewUser(app=client.app) as other_user:
        for _ in range(_free_failed_login_attempts(client) + 1):
            await client.post(url.path, json={"email": blocked_user["email"], "password": "wrong."})

        r = await client.post(url.path, json={"email": other_user["email"], "password": other_user["raw_password"]})

        await assert_status(r, status.HTTP_200_OK)


async def test_successful_login_resets_failed_attempts(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    max_failures_without_block = _free_failed_login_attempts(client)

    async with NewUser(app=client.app) as user:
        for _ in range(2):
            for _ in range(max_failures_without_block):
                r = await client.post(url.path, json={"email": user["email"], "password": "wrong."})
                await assert_status(r, status.HTTP_401_UNAUTHORIZED)

            r = await client.post(url.path, json={"email": user["email"], "password": user["raw_password"]})
            await assert_status(r, status.HTTP_200_OK)


async def test_login_throttle_also_applies_to_unknown_emails(client: TestClient, faker: Faker):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    payload = {"email": faker.unique.email(), "password": "wrong."}

    for _ in range(_free_failed_login_attempts(client) + 1):
        r = await client.post(url.path, json=payload)
        await assert_status(r, status.HTTP_401_UNAUTHORIZED)

    r = await client.post(url.path, json=payload)

    await assert_status(r, status.HTTP_429_TOO_MANY_REQUESTS)
