# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users_bg_tasks import (
    APP_DB_ENGINE_KEY,
    update_expired_users,
)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> EnvVarsDict:
    # disables bg task in users!
    async def _fake_on_cleanup(app: web.Application):
        yield

    mocker.patch(
        "simcore_service_webserver.users.run_background_task_to_monitor_expiration_trial_accounts",
        autospec=True,
        side_effect=_fake_on_cleanup,
    )

    # disables GC
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_GARBAGE_COLLECTOR": "null"}
    )


async def test_update_expired_users(client: TestClient, faker: Faker):

    yesterday = datetime.utcnow() - timedelta(days=1)
    async with NewUser(
        {
            "email": faker.email(),
            "status": UserStatus.ACTIVE.name,
            "expires_at": yesterday,
        },
        client.app,
    ) as user:

        async def _rq_login():
            return await client.post(
                f"{client.app.router['auth_login'].url_for()}",
                json={
                    "email": user["email"],
                    "password": user["raw_password"],
                },
            )

        r1 = await _rq_login()
        await assert_status(r1, web.HTTPOk)

        await update_expired_users(client.app[APP_DB_ENGINE_KEY])

        r2 = await _rq_login()
        await assert_status(r2, web.HTTPUnauthorized)
