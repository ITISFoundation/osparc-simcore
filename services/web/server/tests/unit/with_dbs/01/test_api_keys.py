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
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from simcore_service_webserver.api_keys import _repository as repo
from simcore_service_webserver.api_keys._models import ApiKey
from simcore_service_webserver.api_keys._service import (
    get_or_create_api_key,
    prune_expired_api_keys,
)
from simcore_service_webserver.application_settings import GarbageCollectorSettings
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
async def fake_user_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    faker: Faker,
) -> AsyncIterable[list[int]]:
    assert client.app
    api_keys: list[ApiKey] = [
        await repo.create_api_key(
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
        await repo.delete_api_key(
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
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    disable_gc_manual_guest_users: None,
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
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    disable_gc_manual_guest_users: None,
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
    client: TestClient,
    fake_user_api_keys: list[ApiKey],
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    disable_gc_manual_guest_users: None,
):
    resp = await client.delete("/v0/auth/api-keys/0")
    await assert_status(resp, expected)

    for api_key in fake_user_api_keys:
        resp = await client.delete(f"/v0/auth/api-keys/{api_key.id}")
        await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_200_OK),
)
async def test_create_api_key_with_expiration(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    disable_gc_manual_guest_users: None,
):
    assert client.app

    # create api-keys with expiration interval
    expiration_interval = timedelta(seconds=1)
    resp = await client.post(
        "/v0/auth/api-keys",
        json={"displayName": "foo", "expiration": expiration_interval.seconds},
    )

    data, errors = await assert_status(resp, expected)
    if not errors:
        assert data["displayName"] == "foo"
        assert "apiKey" in data
        assert "apiSecret" in data

        # list created api-key
        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert [d["displayName"] for d in data] == ["foo"]

        # wait for api-key for it to expire and force-run scheduled task
        await asyncio.sleep(expiration_interval.seconds)
        deleted = await prune_expired_api_keys(client.app)
        assert deleted == ["foo"]

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert not data


async def test_get_or_create_api_key(
    client: TestClient,
):
    async with NewUser(
        app=client.app,
    ) as user:

        assert client.app

        options = {
            "user_id": user["id"],
            "product_name": "osparc",
            "display_name": "foo",
        }

        # create once
        created = await get_or_create_api_key(client.app, **options)
        assert created.display_name == "foo"
        assert created.api_key != created.api_secret

        # idempotent
        for _ in range(3):
            assert await get_or_create_api_key(client.app, **options) == created


@pytest.mark.parametrize(
    "user_role,expected",
    _get_user_access_parametrizations(status.HTTP_404_NOT_FOUND),
)
async def test_get_not_existing_api_key(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPException,
    disable_gc_manual_guest_users: None,
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
    webserver_garbage_collector = '{"GARBAGE_COLLECTOR_INTERVAL_S": 30, "GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S": 1}'
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", webserver_garbage_collector)
    return app_environment | {
        "WEBSERVER_GARBAGE_COLLECTOR": webserver_garbage_collector
    }


async def test_prune_expired_api_keys_task_is_triggered(
    app_environment: EnvVarsDict, mocker: MockerFixture, client: TestClient
):
    mock = mocker.patch(
        "simcore_service_webserver.api_keys._service._repository.prune_expired"
    )
    settings = client.server.app[  # type: ignore
        APP_SETTINGS_KEY
    ].WEBSERVER_GARBAGE_COLLECTOR
    assert isinstance(settings, GarbageCollectorSettings)
    await asyncio.sleep(2 * settings.GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S)
    mock.assert_called()
