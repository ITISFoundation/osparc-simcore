# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from fakeredis import FakeAsyncRedis
from pytest_mock import MockerFixture
from redis.exceptions import ConnectionError as RedisConnectionError
from simcore_service_webserver.login import _auth_service, _login_throttle_repository, _login_throttle_service
from simcore_service_webserver.login._login_throttle_service import (
    clear_failed_logins,
    compute_delay_sec,
    get_login_retry_after_sec,
    raise_if_login_throttled,
    register_failed_login,
)
from simcore_service_webserver.login.errors import WrongPasswordError
from simcore_service_webserver.login.settings import LoginThrottleSettings
from simcore_service_webserver.login_auth import _controller_rest as login_auth_controller

_EMAIL = Faker().email()


@pytest.fixture
def throttle_settings() -> LoginThrottleSettings:
    return LoginThrottleSettings(
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
def test_compute_delay_doubles_until_the_maximum(
    throttle_settings: LoginThrottleSettings, failures: int, expected_delay_sec: int
):
    assert compute_delay_sec(failures, settings=throttle_settings) == expected_delay_sec


@pytest.mark.parametrize("base_delay_sec,max_delay_sec", [(10, 5)])
def test_settings_reject_maximum_delay_below_base_delay(base_delay_sec: int, max_delay_sec: int):
    with pytest.raises(ValueError, match="LOGIN_THROTTLE_MAX_DELAY_SEC"):
        LoginThrottleSettings(
            LOGIN_THROTTLE_BASE_DELAY_SEC=base_delay_sec,
            LOGIN_THROTTLE_MAX_DELAY_SEC=max_delay_sec,
        )


async def test_not_throttled_until_free_attempts_are_used(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    for _ in range(throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS):
        await raise_if_login_throttled(app, email=_EMAIL)
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

    assert await get_login_retry_after_sec(app, email=_EMAIL) == 0
    await raise_if_login_throttled(app, email=_EMAIL)

    # the next failure starts the back-off
    await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

    retry_after_sec = await get_login_retry_after_sec(app, email=_EMAIL)
    assert 0 < retry_after_sec <= throttle_settings.LOGIN_THROTTLE_BASE_DELAY_SEC

    with pytest.raises(web.HTTPTooManyRequests) as exc_info:
        await raise_if_login_throttled(app, email=_EMAIL)
    assert int(exc_info.value.headers["Retry-After"]) == retry_after_sec


async def test_back_off_doubles_with_every_failure(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    free = throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS
    for _ in range(free + 2):
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

    # second failure above the free ones: 2 * 2 seconds
    assert 2 < await get_login_retry_after_sec(app, email=_EMAIL) <= 4


async def test_throttling_ignores_case_and_surrounding_spaces_of_the_email(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    for _ in range(throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email=f"  {_EMAIL.upper()} ", settings=throttle_settings)

    assert await get_login_retry_after_sec(app, email=_EMAIL) > 0
    assert await get_login_retry_after_sec(app, email="other@example.com") == 0


async def test_clearing_resets_failures_and_block(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    for _ in range(throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)
    assert await get_login_retry_after_sec(app, email=_EMAIL) > 0

    await clear_failed_logins(app, email=_EMAIL)

    assert await get_login_retry_after_sec(app, email=_EMAIL) == 0
    assert await fake_redis.keys("*") == []


async def test_emails_are_not_stored_in_clear_text(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

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
    guard_client: TestClient, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings
):
    app = guard_client.app
    assert app
    for _ in range(throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1):
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

    response = await guard_client.post("/v0/auth:login-guard", json={"email": _EMAIL.upper(), "password": "x"})

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
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings, mocker: MockerFixture
):
    mocker.patch.object(fake_redis, "pipeline", side_effect=RedisConnectionError("down"))

    with pytest.raises(web.HTTPServiceUnavailable):
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)


async def test_clearing_failed_logins_ignores_redis_errors(
    app: web.Application, fake_redis: FakeAsyncRedis, mocker: MockerFixture
):
    mocker.patch.object(fake_redis, "delete", side_effect=RedisConnectionError("down"))

    await clear_failed_logins(app, email=_EMAIL)


async def test_overlapping_failures_never_shorten_the_back_off(
    app: web.Application, fake_redis: FakeAsyncRedis, throttle_settings: LoginThrottleSettings, mocker: MockerFixture
):
    # failure #7 is handled before the slower failure #6 writes its block
    mocker.patch.object(_login_throttle_repository, "increment_failures", side_effect=[7, 6])
    longest_delay_sec = compute_delay_sec(7, settings=throttle_settings)
    assert compute_delay_sec(6, settings=throttle_settings) < longest_delay_sec

    await register_failed_login(app, email=_EMAIL, settings=throttle_settings)
    await register_failed_login(app, email=_EMAIL, settings=throttle_settings)

    assert await get_login_retry_after_sec(app, email=_EMAIL) == longest_delay_sec


@pytest.fixture
def unresponsive_redis(fake_redis: FakeAsyncRedis, mocker: MockerFixture) -> None:
    async def _never_replies(*args, **kwargs):
        await asyncio.sleep(3600)

    mocker.patch.object(_login_throttle_service, "_REDIS_TIMEOUT_SEC", 0.05)
    for command in ("pttl", "delete"):
        mocker.patch.object(fake_redis, command, side_effect=_never_replies)
    mocker.patch.object(_login_throttle_repository, "increment_failures", side_effect=_never_replies)


async def test_guard_answers_503_when_redis_does_not_reply(guard_client: TestClient, unresponsive_redis: None):
    response = await guard_client.post("/v0/auth:login-guard", json={"email": _EMAIL, "password": "x"})

    assert response.status == 503


async def test_registering_a_failed_login_answers_503_when_redis_does_not_reply(
    app: web.Application, throttle_settings: LoginThrottleSettings, unresponsive_redis: None
):
    with pytest.raises(web.HTTPServiceUnavailable):
        await register_failed_login(app, email=_EMAIL, settings=throttle_settings)


async def test_clearing_failed_logins_ignores_a_redis_that_does_not_reply(
    app: web.Application, unresponsive_redis: None
):
    await clear_failed_logins(app, email=_EMAIL)


async def test_login_guard_accepts_a_very_long_password(guard_client: TestClient):
    response = await guard_client.post("/v0/auth:login-guard", json={"email": _EMAIL, "password": "a" * 100_000})

    assert response.status == 204


@pytest.fixture
def wrong_password_checks(mocker: MockerFixture, throttle_settings: LoginThrottleSettings) -> list[None]:
    calls: list[None] = []

    async def _wrong_password(*_args, **_kwargs):
        calls.append(None)
        await asyncio.sleep(0.01)
        raise WrongPasswordError(user_id=None, product_name="osparc")

    mocker.patch.object(_auth_service, "get_user_or_none", return_value=None)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", side_effect=_wrong_password)
    mocker.patch.object(
        _auth_service, "get_plugin_settings", return_value=SimpleNamespace(LOGIN_THROTTLE=throttle_settings)
    )
    return calls


async def test_concurrent_attempts_cannot_exceed_the_free_attempts(
    app: web.Application,
    fake_redis: FakeAsyncRedis,
    throttle_settings: LoginThrottleSettings,
    wrong_password_checks: list[None],
):
    num_attempts = 20
    product = SimpleNamespace(name="osparc")

    results = await asyncio.gather(
        *(
            _auth_service.authenticate_user(app, email=_EMAIL, password="x", product=product)  # type: ignore[arg-type]  # noqa: S106
            for _ in range(num_attempts)
        ),
        return_exceptions=True,
    )

    allowed_checks = throttle_settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS + 1
    assert len(wrong_password_checks) == allowed_checks
    assert sum(isinstance(r, WrongPasswordError) for r in results) == allowed_checks
    assert sum(isinstance(r, web.HTTPTooManyRequests) for r in results) == num_attempts - allowed_checks


async def test_attempt_is_rejected_when_the_email_lock_is_not_released_in_time(
    app: web.Application, fake_redis: FakeAsyncRedis, wrong_password_checks: list[None], mocker: MockerFixture
):
    mocker.patch.object(_login_throttle_service, "_LOGIN_ATTEMPT_LOCK_WAIT_SEC", 0.2)
    held = _login_throttle_repository.get_login_attempt_lock(
        app, digest=hashlib.sha256(_EMAIL.encode()).hexdigest(), ttl_sec=30, wait_sec=1
    )
    assert await held.acquire()
    product = SimpleNamespace(name="osparc")

    with pytest.raises(web.HTTPTooManyRequests):
        await _auth_service.authenticate_user(app, email=_EMAIL, password="x", product=product)  # type: ignore[arg-type]  # noqa: S106

    assert not wrong_password_checks
