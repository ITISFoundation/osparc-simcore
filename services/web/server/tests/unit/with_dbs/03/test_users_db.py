# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users_db import update_expired_users

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)
YESTERDAY = _NOW - timedelta(days=1)
TOMORROW = _NOW + timedelta(days=1)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: MonkeyPatch
) -> EnvVarsDict:
    # disables GC
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_GARBAGE_COLLECTOR": "null"}
    )


@pytest.mark.parametrize("expires_at", (YESTERDAY, TOMORROW, None))
async def test_update_expired_users(
    expires_at: Optional[datetime], client: TestClient, faker: Faker
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
