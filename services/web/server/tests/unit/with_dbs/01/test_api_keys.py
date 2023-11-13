# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from datetime import timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver.api_keys._api import prune_expired_api_keys
from simcore_service_webserver.api_keys._db import ApiKeyRepo
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
async def fake_user_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    assert client.app
    names = ["foo", "bar", "beta", "alpha"]
    repo = ApiKeyRepo.create_from_app(app=client.app)

    for name in names:
        await repo.create(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            display_name=name,
            expiration=None,
            api_key=f"{name}-key",
            api_secret=f"{name}-secret",
        )

    yield names

    for name in names:
        await repo.delete_by_name(
            display_name=name,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


_USER_ACCESS_PARAMETERS = [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    *((UserRole.USER, web.HTTPOk) for role in UserRole if role > UserRole.GUEST),
]


@pytest.mark.parametrize(
    "user_role,expected",
    _USER_ACCESS_PARAMETERS,
)
async def test_list_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
    disable_gc_manual_guest_users: None,
):
    resp = await client.get("/v0/auth/api-keys")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert not data


@pytest.mark.parametrize("user_role,expected", _USER_ACCESS_PARAMETERS)
async def test_create_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
    disable_gc_manual_guest_users: None,
):
    display_name = "foo"
    resp = await client.post("/v0/auth/api-keys", json={"display_name": display_name})

    data, errors = await assert_status(resp, expected)

    if not errors:
        assert data["display_name"] == display_name
        assert "api_key" in data
        assert "api_secret" in data

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert sorted(data) == [
            display_name,
        ]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        *(
            (UserRole.USER, web.HTTPNoContent)
            for role in UserRole
            if role > UserRole.GUEST
        ),
    ],
)
async def test_delete_api_keys(
    client: TestClient,
    fake_user_api_keys,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
    disable_gc_manual_guest_users: None,
):
    resp = await client.delete("/v0/auth/api-keys", json={"display_name": "foo"})
    await assert_status(resp, expected)

    for name in fake_user_api_keys:
        resp = await client.delete("/v0/auth/api-keys", json={"display_name": name})
        await assert_status(resp, expected)


@pytest.mark.parametrize("user_role,expected", _USER_ACCESS_PARAMETERS)
async def test_create_api_key_with_expiration(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
    disable_gc_manual_guest_users: None,
):
    assert client.app

    # create api-keys with expiration interval
    expiration_interval = timedelta(seconds=1)
    resp = await client.post(
        "/v0/auth/api-keys",
        json={"display_name": "foo", "expiration": expiration_interval.seconds},
    )

    data, errors = await assert_status(resp, expected)
    if not errors:
        assert data["display_name"] == "foo"
        assert "api_key" in data
        assert "api_secret" in data

        # list created api-key
        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert data == ["foo"]

        # wait for api-key for it to expire and force-run scheduled task
        await asyncio.sleep(expiration_interval.seconds)
        deleted = await prune_expired_api_keys(client.app)
        assert deleted == ["foo"]

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert not data
