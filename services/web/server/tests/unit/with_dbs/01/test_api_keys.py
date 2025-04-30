# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import AsyncIterable
from datetime import timedelta
from http import HTTPStatus
from http.client import HTTPException

import pytest
import tenacity
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.products import ProductName
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.api_keys import _repository, api_keys_service
from simcore_service_webserver.api_keys.models import ApiKey
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.db.models import UserRole
from tenacity import (
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)


@pytest.fixture
async def fake_user_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    faker: Faker,
) -> AsyncIterable[list[ApiKey]]:
    assert client.app

    api_keys: list[ApiKey] = [
        await _repository.create_api_key(
            client.app,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            display_name=faker.pystr(),
            expiration=None,
            api_key=faker.pystr(),
            api_secret=faker.pystr(),
        )
        for _ in range(5)
    ]

    yield api_keys

    for api_key in api_keys:
        await _repository.delete_api_key(
            client.app,
            api_key_id=api_key.id,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


def _get_user_access_parametrizations(expected_authed_status_code):
    return [
        pytest.param(UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        pytest.param(UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        *(
            pytest.param(r, expected_authed_status_code)
            for r in UserRole
            if r > UserRole.GUEST
        ),
    ]


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_200_OK),
)
async def test_list_api_keys(
    disabled_setup_garbage_collector: MockType,
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    resp = await client.get("/v0/auth/api-keys")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert not data


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_200_OK),
)
async def test_create_api_key(
    disabled_setup_garbage_collector: MockType,
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    display_name = "foo"
    resp = await client.post("/v0/auth/api-keys", json={"displayName": display_name})

    data, errors = await assert_status(resp, expected)

    if not errors:
        assert data["displayName"] == display_name
        assert "apiKey" in data
        assert "apiSecret" in data

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert [d["displayName"] for d in data] == [display_name]


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_204_NO_CONTENT),
)
async def test_delete_api_keys(
    disabled_setup_garbage_collector: MockType,
    client: TestClient,
    fake_user_api_keys: list[ApiKey],
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    resp = await client.delete("/v0/auth/api-keys/0")
    await assert_status(resp, expected)

    for api_key in fake_user_api_keys:
        resp = await client.delete(f"/v0/auth/api-keys/{api_key.id}")
        await assert_status(resp, expected)


EXPIRATION_WAIT_FACTOR = 1.2


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_200_OK),
)
async def test_create_api_key_with_expiration(
    disabled_setup_garbage_collector: MockType,
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    mocker: MockerFixture,
):
    assert client.app

    # test gc is actually disabled
    gc_prune_mock = mocker.patch(
        "simcore_service_webserver.garbage_collector._tasks_api_keys.create_background_task_to_prune_api_keys",
        spec=True,
    )
    assert not gc_prune_mock.called

    expected_api_key = "foo"

    # create api-keys with expiration interval
    expiration_interval = timedelta(seconds=1)
    resp = await client.post(
        "/v0/auth/api-keys",
        json={
            "displayName": expected_api_key,
            "expiration": expiration_interval.seconds,
        },
    )

    data, errors = await assert_status(resp, expected)
    if not errors:
        assert data["displayName"] == expected_api_key
        assert "apiKey" in data
        assert "apiSecret" in data

        # list created api-key
        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert [d["displayName"] for d in data] == [expected_api_key]

        # wait for api-key for it to expire and force-run scheduled task
        await asyncio.sleep(EXPIRATION_WAIT_FACTOR * expiration_interval.seconds)

        deleted = await api_keys_service.prune_expired_api_keys(client.app)
        assert deleted == [expected_api_key]

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert not data


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_404_NOT_FOUND),
)
async def test_get_not_existing_api_key(
    disabled_setup_garbage_collector: MockType,
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPException,
):
    resp = await client.get("/v0/auth/api-keys/42")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert data is None


@pytest.fixture
async def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": '{"GARBAGE_COLLECTOR_INTERVAL_S": 30, "GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S": 1}'
        },
    )


async def test_prune_expired_api_keys_task_is_triggered(
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
    client: TestClient,
):
    assert app_environment["WEBSERVER_GARBAGE_COLLECTOR"] is not None

    delete_expired_spy = mocker.spy(_repository, "delete_expired_api_keys")

    assert client.app

    settings: ApplicationSettings = get_application_settings(client.app)
    assert settings.WEBSERVER_GARBAGE_COLLECTOR

    assert not delete_expired_spy.called

    async for attempt in tenacity.AsyncRetrying(
        stop=stop_after_delay(
            timedelta(
                seconds=EXPIRATION_WAIT_FACTOR
                * settings.WEBSERVER_GARBAGE_COLLECTOR.GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S
            )
        ),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            delete_expired_spy.assert_called()
