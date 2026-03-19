# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable

import pytest
import sqlalchemy as sa
from pytest_simcore.helpers import postgres_users
from simcore_postgres_database.webserver_models import (
    GroupType,
    groups,
    user_to_groups,
    users,
)
from sqlalchemy import func, literal_column, select
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


async def test_user_group_uniqueness(
    asyncpg_connection: AsyncConnection,
    create_fake_group: Callable,
    create_fake_user: Callable,
):
    rory_group = await create_fake_group(asyncpg_connection, name="Rory Storm and the Hurricanes")
    ringo = await create_fake_user(asyncpg_connection, name="Ringo", group=rory_group)
    # test unique user/group pair
    with pytest.raises(sa.exc.IntegrityError, match="user_to_groups_uid_gid_key"):
        await asyncpg_connection.execute(user_to_groups.insert().values(uid=ringo["id"], gid=rory_group["gid"]))

    # Checks implementation of simcore_service_webserver/groups_api.py:get_group_from_gid
    res = await asyncpg_connection.execute(groups.select().where(groups.c.gid == rory_group["gid"]))

    the_one = res.mappings().first()
    assert the_one is not None
    assert the_one["type"]

    with pytest.raises(sa.exc.ResourceClosedError):
        res.fetchone()


async def test_all_group(
    asyncpg_connection: AsyncConnection,
):
    # now check the only available group is the all group
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == 1

    result = await asyncpg_connection.execute(groups.select().where(groups.c.type == GroupType.EVERYONE))
    all_group_gid = result.mappings().one()["gid"]
    assert all_group_gid == 1  # it's the first group so it gets a 1
    # try removing the all group
    with pytest.raises(sa.exc.InternalError):
        await asyncpg_connection.execute(groups.delete().where(groups.c.gid == all_group_gid))

    # check adding a user is automatically added to the all group
    user_id = await postgres_users.insert_user_and_secrets(asyncpg_connection)
    result = await asyncpg_connection.execute(users.select().where(users.c.id == user_id))
    user: RowMapping = result.mappings().one()

    result = await asyncpg_connection.execute(user_to_groups.select().where(user_to_groups.c.gid == all_group_gid))
    user_to_groups_row: RowMapping = result.mappings().one()
    assert user_to_groups_row["uid"] == user["id"]
    assert user_to_groups_row["gid"] == all_group_gid

    # try removing the all group
    with pytest.raises(sa.exc.InternalError):
        await asyncpg_connection.execute(groups.delete().where(groups.c.gid == all_group_gid))

    # remove the user now
    await asyncpg_connection.execute(users.delete().where(users.c.id == user["id"]))
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 0

    # check the all group still exists
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == 1
    result = await asyncpg_connection.execute(groups.select().where(groups.c.type == GroupType.EVERYONE))
    all_group_gid = result.mappings().one()["gid"]
    assert all_group_gid == 1  # it's the first group so it gets a 1


async def test_own_group(
    asyncpg_connection: AsyncConnection,
):
    user_id = await postgres_users.insert_user_and_secrets(asyncpg_connection)

    # now fetch the same user that shall have a primary group set by the db
    result = await asyncpg_connection.execute(users.select().where(users.c.id == user_id))
    user: RowMapping = result.mappings().one()
    assert user["primary_gid"]

    # now check there is a primary group
    result = await asyncpg_connection.execute(groups.select().where(groups.c.type == GroupType.PRIMARY))
    primary_group: RowMapping = result.mappings().one()
    assert primary_group["gid"] == user["primary_gid"]

    groups_count = await asyncpg_connection.scalar(
        select(func.count(groups.c.gid)).where(groups.c.gid == user["primary_gid"])
    )
    assert groups_count == 1

    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == 2  # own group + all group

    # try removing the primary group
    with pytest.raises(sa.exc.IntegrityError):
        await asyncpg_connection.execute(groups.delete().where(groups.c.gid == user["primary_gid"]))

    # now remove the users should remove the primary group
    await asyncpg_connection.execute(users.delete().where(users.c.id == user["id"]))
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 0
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == 1  # the all group is still around
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count)


async def test_group(
    asyncpg_connection: AsyncConnection,
    create_fake_group: Callable,
    create_fake_user: Callable,
):
    rory_group = await create_fake_group(asyncpg_connection, name="Rory Storm and the Hurricanes")
    quarrymen_group = await create_fake_group(asyncpg_connection, name="The Quarrymen")
    await create_fake_user(asyncpg_connection, name="John", group=quarrymen_group)
    await create_fake_user(asyncpg_connection, name="Paul", group=quarrymen_group)
    await create_fake_user(asyncpg_connection, name="Georges", group=quarrymen_group)
    pete = await create_fake_user(asyncpg_connection, name="Pete", group=quarrymen_group)
    ringo = await create_fake_user(asyncpg_connection, name="Ringo", group=rory_group)

    # rationale: following linux user/group system, each user has its own group (primary group) + whatever other group
    #  (secondary groups)
    # check DB contents
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 5
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == (users_count + 2 + 1)  # user primary groups, other groups, all group
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count + users_count)

    # change group name
    result = await asyncpg_connection.execute(
        groups.update()
        .where(groups.c.gid == quarrymen_group["gid"])
        .values(name="The Beatles")
        .returning(literal_column("*"))
    )
    beatles_group = result.mappings().one()
    assert beatles_group["modified"] > quarrymen_group["modified"]

    # delete 1 user
    await asyncpg_connection.execute(users.delete().where(users.c.id == pete["id"]))

    # check DB contents
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 4
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == (users_count + 2 + 1)
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count + users_count)

    # add one user to another group
    await asyncpg_connection.execute(user_to_groups.insert().values(uid=ringo["id"], gid=beatles_group["gid"]))

    # check DB contents
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 4
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == (users_count + 2 + 1)
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count + 1 + users_count)

    # delete 1 group
    await asyncpg_connection.execute(groups.delete().where(groups.c.gid == rory_group["gid"]))

    # check DB contents
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 4
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == (users_count + 1 + 1)
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count + users_count)

    # delete the other group
    await asyncpg_connection.execute(groups.delete().where(groups.c.gid == beatles_group["gid"]))

    # check DB contents
    users_count = await asyncpg_connection.scalar(select(func.count()).select_from(users))
    assert users_count == 4
    groups_count = await asyncpg_connection.scalar(select(func.count()).select_from(groups))
    assert groups_count == (users_count + 0 + 1)
    relations_count = await asyncpg_connection.scalar(select(func.count()).select_from(user_to_groups))
    assert relations_count == (users_count + users_count)
