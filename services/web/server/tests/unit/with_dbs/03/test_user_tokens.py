# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import random
from collections.abc import AsyncIterator
from copy import deepcopy
from http import HTTPStatus
from itertools import repeat
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_tokens import (
    create_token_in_db,
    delete_all_tokens_from_db,
    get_token_from_db,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.db.plugin import get_database_engine_legacy


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


@pytest.fixture
async def tokens_db_cleanup(
    logged_user: UserInfoDict,
    client: TestClient,
) -> AsyncIterator[None]:
    assert client.app
    engine = get_database_engine_legacy(client.app)

    yield None

    await delete_all_tokens_from_db(engine)


@pytest.fixture
async def fake_tokens(
    client: TestClient,
    logged_user: UserInfoDict,
    tokens_db_cleanup: None,
    faker: Faker,
) -> list[dict[str, Any]]:
    all_tokens = []
    assert client.app

    # TODO: automatically create data from oas!
    # See api/specs/webserver/v0/components/schemas/me.yaml
    for _ in repeat(None, 5):
        # TODO: add tokens from other users
        data = {
            "service": faker.word(ext_word_list=None),
            "token_key": faker.md5(raw_output=False),
            "token_secret": faker.md5(raw_output=False),
        }
        await create_token_in_db(
            get_database_engine_legacy(client.app),
            user_id=logged_user["id"],
            token_service=data["service"],
            token_data=data,
        )
        all_tokens.append(data)
    return all_tokens


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_201_CREATED),
        (UserRole.TESTER, status.HTTP_201_CREATED),
    ],
)
async def test_create_token(
    client: TestClient,
    logged_user: UserInfoDict,
    tokens_db_cleanup: None,
    expected: HTTPStatus,
    faker: Faker,
):
    assert client.app

    url = client.app.router["create_token"].url_for()
    assert str(url) == "/v0/me/tokens"

    token = {
        "service": "pennsieve",
        "token_key": faker.uuid4(),
        "token_secret": faker.uuid4(),
    }

    resp = await client.post(url.path, json=token)
    data, error = await assert_status(resp, expected)
    if not error:
        db_token = await get_token_from_db(
            get_database_engine_legacy(client.app), token_data=token
        )
        assert db_token
        assert db_token["token_data"] == token
        assert db_token["user_id"] == logged_user["id"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_read_token(
    client: TestClient,
    logged_user: UserInfoDict,
    tokens_db_cleanup: None,
    fake_tokens: list[dict[str, Any]],
    expected: HTTPStatus,
):
    assert client.app
    # list all
    url = f"{client.app.router['list_tokens'].url_for()}"
    assert str(url) == "/v0/me/tokens"

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        expected_token = deepcopy(random.choice(fake_tokens))
        sid = expected_token["service"]

        # get one
        url = client.app.router["get_token"].url_for(service=sid)
        assert f"/v0/me/tokens/{sid}" == str(url)
        resp = await client.get(url.path)

        data, error = await assert_status(resp, expected)

        expected_token["token_key"] = expected_token["token_key"]
        expected_token["token_secret"] = None
        assert data == expected_token, "list and read item are both read operations"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_delete_token(
    client: TestClient,
    logged_user: UserInfoDict,
    tokens_db_cleanup: None,
    fake_tokens: list[dict[str, Any]],
    expected: HTTPStatus,
):
    assert client.app

    sid = fake_tokens[0]["service"]

    url = client.app.router["delete_token"].url_for(service=sid)
    assert f"/v0/me/tokens/{sid}" == str(url)

    resp = await client.delete(url.path)

    _, error = await assert_status(resp, expected)

    if not error:
        assert not (
            await get_token_from_db(
                get_database_engine_legacy(client.app), token_service=sid
            )
        )
