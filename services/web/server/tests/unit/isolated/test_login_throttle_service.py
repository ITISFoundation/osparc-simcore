# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from fakeredis import FakeAsyncRedis
from pytest_mock import MockerFixture
from redis.exceptions import ConnectionError as RedisConnectionError
from simcore_service_webserver.login import _login_throttle_repository
from simcore_service_webserver.login._login_throttle_service import (
    clear_failed_logins,
    compute_delay_sec,
    get_login_retry_after_sec,
    raise_if_login_throttled,
    register_failed_login,
)
from simcore_service_webserver.login.settings import LoginSettings
from simcore_service_webserver.login_auth import _controller_rest as login_auth_controller

_EMAIL = "user@example.com"


@pytest.fixture
def login_settings() -> LoginSettings:
    return LoginSettings(
        LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
        LOGIN_TWILIO=None,
        LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS=3,
        LOGIN_THROTTLE_BASE_DELAY_SEC=2,
        LOGIN_THROTTLE_MAX_DELAY_SEC=60,
        LOGIN_THROTTLE_WINDOW_SEC=3600,
    )


@pytest.fixture
async def fake_redis(mocker: MockerFixture) -> AsyncIterator[FakeAsyncRedis]:
    redis_client = FakeAsyncRedis()
    mocker.patch.object(_login_throttle_repository, "get_redis_login_throttle_client", return_value=redis_client)
    yield redis_client
    await redis_client.aclose()


@pytest.fixture
def app() -> web.Application:
    return web.Application()


@pytest.mark.parametrize(
    "failures,expected_delay_sec",
    [
        (0, 0),
        (3, 0),  # last free attempt
        (4, 2),
        (5, 4),
        (6, 8),
        (7, 16),
        (8, 32),
        (9, 60),  # capped
        (10_000, 60),  # no overflow
    ],
)
def test_compute_delay_doubles_until_the_maximum(login_settings: LoginSettings, failures: int, expected_delay_sec: int):
    assert compute_delay_sec(failures, settings=login_settings) == expected_delay_sec


@pytest.mark.parametrize("base_delay_sec,max_delay_sec", [(10, 5)])
def test_settings_reject_maximum_delay_below_base_delay(base_delay_sec: int, max_delay_sec: int):
    with pytest.raises(ValueError, match="LOGIN_THROTTLE_MAX_DELAY_SEC"):
        LoginSettings(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
            LOGIN_THROTTLE_BASE_DELAY_SEC=base_delay_sec,
            LOGIN_THROTTLE_MAX_DELAY_SEC=max_delay_sec,
        )


async def test_not_throttled_until_free_attempts_are_used(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    for _ in range(login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS):
        await raise_if_login_throttled(app, email=_EMAIL)
        await register_failed_login(app, email=_EMAIL, settings=login_settings)

    assert await get_login_retry_after_sec(app, email=_EMAIL) == 0
    await raise_if_login_throttled(app, email=_EMAIL)

    # the next failure starts the back-off
    await register_failed_login(app, email=_EMAIL, settings=login_settings)

    retry_after_sec = await get_login_retry_after_sec(app, email=_EMAIL)
    assert 0 < retry_after_sec <= login_settings.LOGIN_THROTTLE_BASE_DELAY_SEC

    with pytest.raises(web.HTTPTooManyRequests) as exc_info:
        await raise_if_login_throttled(app, email=_EMAIL)
    assert int(exc_info.value.headers["Retry-After"]) == retry_after_sec


async def test_back_off_doubles_with_every_failure(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    free = login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS
    for _ in range(free + 2):
        await register_failed_login(app, email=_EMAIL, settings=login_settings)

    # second failure above the free ones: 2 * 2 seconds
    assert 2 < await get_login_retry_after_sec(app, email=_EMAIL) <= 4


async def test_throttling_ignores_case_and_surrounding_spaces_of_the_email(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    for _ in range(login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email="  User@Example.COM ", settings=login_settings)

    assert await get_login_retry_after_sec(app, email=_EMAIL) > 0
    assert await get_login_retry_after_sec(app, email="other@example.com") == 0


async def test_clearing_resets_failures_and_block(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    for _ in range(login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email=_EMAIL, settings=login_settings)
    assert await get_login_retry_after_sec(app, email=_EMAIL) > 0

    await clear_failed_logins(app, email=_EMAIL)

    assert await get_login_retry_after_sec(app, email=_EMAIL) == 0
    assert await fake_redis.keys("*") == []


async def test_emails_are_not_stored_in_clear_text(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    await register_failed_login(app, email=_EMAIL, settings=login_settings)

    keys = [key.decode() for key in await fake_redis.keys("*")]
    assert keys
    assert all(_EMAIL not in key for key in keys)


@pytest.fixture
async def guard_client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    fake_redis: FakeAsyncRedis,
) -> TestClient:
    app = web.Application()
    app.add_routes(login_auth_controller.routes)
    return await aiohttp_client(app)


async def test_login_guard_allows_emails_that_are_not_in_back_off(guard_client: TestClient):
    response = await guard_client.post("/v0/auth:login-guard", json={"email": _EMAIL, "password": "irrelevant"})

    assert response.status == 204


async def test_login_guard_rejects_emails_in_back_off(
    guard_client: TestClient, fake_redis: FakeAsyncRedis, login_settings: LoginSettings
):
    app = guard_client.app
    assert app
    for _ in range(login_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email=_EMAIL, settings=login_settings)

    response = await guard_client.post("/v0/auth:login-guard", json={"email": "USER@example.com", "password": "x"})

    assert response.status == 429
    assert int(response.headers["Retry-After"]) > 0

    other = await guard_client.post("/v0/auth:login-guard", json={"email": "other@example.com", "password": "x"})
    assert other.status == 204


@pytest.mark.parametrize("body", [b"", b"not json", b'{"password": "no email"}', b'{"email": "not-an-email"}'])
async def test_login_guard_lets_invalid_bodies_through_to_the_login_endpoint(guard_client: TestClient, body: bytes):
    response = await guard_client.post("/v0/auth:login-guard", data=body)

    assert response.status == 204


async def test_login_guard_answers_503_when_redis_fails(
    guard_client: TestClient, fake_redis: FakeAsyncRedis, mocker: MockerFixture
):
    mocker.patch.object(fake_redis, "pttl", side_effect=RedisConnectionError("down"))

    response = await guard_client.post("/v0/auth:login-guard", json={"email": _EMAIL, "password": "x"})

    assert response.status == 503


async def test_registering_a_failed_login_answers_503_when_redis_fails(
    app: web.Application, fake_redis: FakeAsyncRedis, login_settings: LoginSettings, mocker: MockerFixture
):
    mocker.patch.object(fake_redis, "pipeline", side_effect=RedisConnectionError("down"))

    with pytest.raises(web.HTTPServiceUnavailable):
        await register_failed_login(app, email=_EMAIL, settings=login_settings)


async def test_clearing_failed_logins_ignores_redis_errors(
    app: web.Application, fake_redis: FakeAsyncRedis, mocker: MockerFixture
):
    mocker.patch.object(fake_redis, "delete", side_effect=RedisConnectionError("down"))

    await clear_failed_logins(app, email=_EMAIL)
