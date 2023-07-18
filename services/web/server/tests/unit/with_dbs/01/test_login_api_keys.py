# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from datetime import timedelta
from pprint import pformat
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from pydantic import BaseModel
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_service_webserver._constants import RQT_USERID_KEY
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.login.api_keys_db import prune_expired_api_keys
from simcore_service_webserver.login.api_keys_handlers import (
    ApiKeyCreate,
    ApiKeyGet,
    ApiKeyRepo,
)


@pytest.fixture()
async def fake_user_api_keys(client: TestClient, logged_user):
    names = ["foo", "bar", "beta", "alpha"]

    mock_request = make_mocked_request(method="GET", path="/foo", app=client.app)
    mock_request[RQT_USERID_KEY] = logged_user["id"]

    repo = ApiKeyRepo(mock_request)

    for name in names:
        await repo.create(
            ApiKeyCreate(display_name=name, expiration=None),
            api_key=f"{name}-key",
            api_secret=f"{name}-secret",
        )

    yield names

    for name in names:
        await repo.delete(name)


USER_ACCESS_PARAMETERS = [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
]


@pytest.mark.parametrize(
    "user_role,expected",
    USER_ACCESS_PARAMETERS,
)
async def test_list_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected,
    disable_gc_manual_guest_users: None,
):
    resp = await client.get("/v0/auth/api-keys")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert not data


@pytest.mark.parametrize("user_role,expected", USER_ACCESS_PARAMETERS)
async def test_create_api_keys(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected,
    disable_gc_manual_guest_users: None,
):
    resp = await client.post("/v0/auth/api-keys", json={"display_name": "foo"})

    data, errors = await assert_status(resp, expected)

    if not errors:
        assert data["display_name"] == "foo"
        assert "api_key" in data
        assert "api_secret" in data

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert sorted(data) == [
            "foo",
        ]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPNoContent),
        (UserRole.TESTER, web.HTTPNoContent),
    ],
)
async def test_delete_api_keys(
    client: TestClient,
    fake_user_api_keys,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected,
    disable_gc_manual_guest_users: None,
):
    resp = await client.delete("/v0/auth/api-keys", json={"display_name": "foo"})
    await assert_status(resp, expected)

    for name in fake_user_api_keys:
        resp = await client.delete("/v0/auth/api-keys", json={"display_name": name})
        await assert_status(resp, expected)


@pytest.mark.parametrize("user_role,expected", USER_ACCESS_PARAMETERS)
async def test_create_api_key_with_expiration(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected,
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


@pytest.mark.parametrize(
    "model_cls",
    [ApiKeyCreate, ApiKeyGet],
)
def test_api_keys_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
) -> None:
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_obj = model_cls(**example)
        assert model_obj.json(**RESPONSE_MODEL_POLICY)
