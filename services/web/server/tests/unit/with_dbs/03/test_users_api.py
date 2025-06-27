# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.groups import EVERYONE_GROUP_ID
from models_library.users import UserID, UserNameID
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users.api import (
    delete_user_without_projects,
    get_guest_user_ids_and_names,
    get_user,
    get_user_credentials,
    get_user_display_and_id_names,
    get_user_fullname,
    get_user_id_from_gid,
    get_user_name_and_email,
    get_user_role,
    get_users_in_group,
    set_user_as_deleted,
    update_expired_users,
)
from simcore_service_webserver.users.exceptions import UserNotFoundError


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


async def test_reading_a_user(client: TestClient, faker: Faker, user: UserInfoDict):
    assert client.app
    user_id = user["id"]

    got = await get_user(client.app, user_id=user_id)

    keys = set(got.keys()).intersection(user.keys())

    assert {k: got[k] for k in keys} == {k: user[k] for k in keys}

    user_primary_group_id = got["primary_gid"]

    email, phash, display = await get_user_credentials(client.app, user_id=user_id)
    assert email == user["email"]
    assert phash
    assert display

    # NOTE: designed to always provide some display name
    got = await get_user_display_and_id_names(client.app, user_id=user_id)
    assert (
        got.first_name.lower() == (user.get("first_name") or user.get("name")).lower()
    )
    assert got.last_name.lower() == (user.get("last_name") or "").lower()
    assert got.name == user["name"]

    got = await get_user_fullname(client.app, user_id=user_id)
    assert got == {k: v for k, v in user.items() if k in got}

    got = await get_user_name_and_email(client.app, user_id=user_id)
    assert got.email == user["email"]
    assert got.name == user["name"]

    got = await get_user_role(client.app, user_id=user_id)
    assert got == user["role"]

    got = await get_user_id_from_gid(client.app, primary_gid=user_primary_group_id)
    assert got == user_id

    everyone = await get_users_in_group(client.app, gid=EVERYONE_GROUP_ID)
    assert user_id in everyone
    assert len(everyone) == 1


async def test_listing_users(client: TestClient, faker: Faker, user: UserInfoDict):
    assert client.app

    guests = await get_guest_user_ids_and_names(client.app)
    assert not guests

    async with NewUser(user_data={"role": UserRole.GUEST}, app=client.app) as guest:
        got = await get_guest_user_ids_and_names(client.app)
        assert (guest["id"], guest["name"]) in TypeAdapter(
            list[tuple[UserID, UserNameID]]
        ).validate_python(got)

    guests = await get_guest_user_ids_and_names(client.app)
    assert not guests


async def test_deleting_a_user(
    client: TestClient,
    faker: Faker,
    user: UserInfoDict,
):
    assert client.app
    user_id = user["id"]

    # exists
    got = await get_user(client.app, user_id=user_id)
    assert got["id"] == user_id

    # MARK as deleted
    await set_user_as_deleted(client.app, user_id=user_id)

    got = await get_user(client.app, user_id=user_id)
    assert got["id"] == user_id

    # DO DELETE
    await delete_user_without_projects(client.app, user_id=user_id)

    # does not exist
    with pytest.raises(UserNotFoundError):
        await get_user(client.app, user_id=user_id)


_NOW = datetime.now()  # WARNING: UTC affects here since expires is not defined as UTC
YESTERDAY = _NOW - timedelta(days=1)
TOMORROW = _NOW + timedelta(days=1)


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
        await assert_status(r1, status.HTTP_200_OK)

        # apply update
        expired = await update_expired_users(client.app)
        if has_expired:
            assert expired == [user["id"]]
        else:
            assert not expired

        # after update
        r2 = await _rq_login()
        await assert_status(
            r2, status.HTTP_401_UNAUTHORIZED if has_expired else status.HTTP_200_OK
        )


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
