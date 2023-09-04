# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import arrow
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users.api import (
    get_user_name_and_email,
    update_expired_users,
)

_NOW = arrow.utcnow().datetime
YESTERDAY = _NOW - timedelta(days=1)
TOMORROW = _NOW + timedelta(days=1)


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


@pytest.mark.parametrize("expires_at", [YESTERDAY, TOMORROW, None])
async def test_update_expired_users(
    expires_at: datetime | None, client: TestClient, faker: Faker
):
    has_expired = expires_at == YESTERDAY
    async with NewUser(
        {
            "email": faker.email(),
            "status": UserStatus.ACTIVE.name,
            "expires_at": expires_at,
        },
        client.app,
    ) as user:
        assert client.app

        async def _rq_login():
            assert client.app
            return await client.post(
                f"{client.app.router['auth_login'].url_for()}",
                json={
                    "email": user["email"],
                    "password": user["raw_password"],
                },
            )

        # before update
        r1 = await _rq_login()
        await assert_status(r1, web.HTTPOk)

        # apply update
        expired = await update_expired_users(client.app[APP_DB_ENGINE_KEY])
        if has_expired:
            assert expired == [user["id"]]
        else:
            assert not expired

        # after update
        r2 = await _rq_login()
        await assert_status(r2, web.HTTPUnauthorized if has_expired else web.HTTPOk)


async def test_get_username_and_email(client: TestClient, faker: Faker):
    assert client.app

    async with NewUser(
        {
            "email": faker.email(),
        },
        client.app,
    ) as user:
        assert await get_user_name_and_email(client.app, user_id=user["id"]) == (
            user["name"],
            user["email"],
        )
