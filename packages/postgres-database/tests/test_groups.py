# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter


from typing import Awaitable, Callable, Optional, Union

import aiopg.sa.exc
import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from psycopg2.errors import ForeignKeyViolation, RaiseException, UniqueViolation
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import (
    GroupType,
    groups,
    user_to_groups,
    users,
)
from sqlalchemy import func, literal_column, select


async def test_user_group_uniqueness(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]],
    create_fake_group: Callable,
    create_fake_user: Callable,
):
    engine = await make_engine()
    sync_engine = make_engine(is_async=False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)

    async with engine.acquire() as conn:
        rory_group = await create_fake_group(conn, name="Rory Storm and the Hurricanes")
        ringo = await create_fake_user(conn, name="Ringo", group=rory_group)
        # test unique user/group pair
        with pytest.raises(UniqueViolation, match="user_to_groups_uid_gid_key"):
            await conn.execute(
                user_to_groups.insert().values(uid=ringo.id, gid=rory_group.gid)
            )

        # Checks implementation of simcore_service_webserver/groups_api.py:get_group_from_gid
        res: ResultProxy = await conn.execute(
            groups.select().where(groups.c.gid == rory_group.gid)
        )

        the_one: Optional[RowProxy] = await res.first()
        assert the_one.type == the_one["type"]

        with pytest.raises(aiopg.sa.exc.ResourceClosedError):
            await res.fetchone()


async def test_all_group(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]]
):
    engine = await make_engine()
    sync_engine = make_engine(is_async=False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        # now check the only available group is the all group
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == 1

        result = await conn.execute(
            groups.select().where(groups.c.type == GroupType.EVERYONE)
        )
        all_group_gid = (await result.fetchone()).gid
        assert all_group_gid == 1  # it's the first group so it gets a 1
        # try removing the all group
        with pytest.raises(RaiseException):
            await conn.execute(groups.delete().where(groups.c.gid == all_group_gid))

        # check adding a user is automatically added to the all group
        result = await conn.execute(
            users.insert().values(**random_user()).returning(literal_column("*"))
        )
        user: RowProxy = await result.fetchone()

        result = await conn.execute(
            user_to_groups.select().where(user_to_groups.c.gid == all_group_gid)
        )
        user_to_groups_row: RowProxy = await result.fetchone()
        assert user_to_groups_row.uid == user.id
        assert user_to_groups_row.gid == all_group_gid

        # try removing the all group
        with pytest.raises(RaiseException):
            await conn.execute(groups.delete().where(groups.c.gid == all_group_gid))

        # remove the user now
        await conn.execute(users.delete().where(users.c.id == user.id))
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 0

        # check the all group still exists
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == 1
        result = await conn.execute(
            groups.select().where(groups.c.type == GroupType.EVERYONE)
        )
        all_group_gid = (await result.fetchone()).gid
        assert all_group_gid == 1  # it's the first group so it gets a 1


async def test_own_group(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]]
):
    engine = await make_engine()
    sync_engine = make_engine(is_async=False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        result = await conn.execute(
            users.insert().values(**random_user()).returning(literal_column("*"))
        )
        user: RowProxy = await result.fetchone()
        assert not user.primary_gid

        # now fetch the same user that shall have a primary group set by the db
        result = await conn.execute(users.select().where(users.c.id == user.id))
        user: RowProxy = await result.fetchone()
        assert user.primary_gid

        # now check there is a primary group
        result = await conn.execute(
            groups.select().where(groups.c.type == GroupType.PRIMARY)
        )
        primary_group: RowProxy = await result.fetchone()
        assert primary_group.gid == user.primary_gid

        groups_count = await conn.scalar(
            select([func.count(groups.c.gid)]).where(groups.c.gid == user.primary_gid)
        )
        assert groups_count == 1

        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == 2  # own group + all group

        # try removing the primary group
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(groups.delete().where(groups.c.gid == user.primary_gid))

        # now remove the users should remove the primary group
        await conn.execute(users.delete().where(users.c.id == user.id))
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 0
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == 1  # the all group is still around
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count)


async def test_group(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]],
    create_fake_group: Callable,
    create_fake_user: Callable,
):
    engine = await make_engine()
    sync_engine = make_engine(is_async=False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        rory_group = await create_fake_group(conn, name="Rory Storm and the Hurricanes")
        quarrymen_group = await create_fake_group(conn, name="The Quarrymen")
        await create_fake_user(conn, name="John", group=quarrymen_group)
        await create_fake_user(conn, name="Paul", group=quarrymen_group)
        await create_fake_user(conn, name="Georges", group=quarrymen_group)
        pete = await create_fake_user(conn, name="Pete", group=quarrymen_group)
        ringo = await create_fake_user(conn, name="Ringo", group=rory_group)

        # rationale: following linux user/group system, each user has its own group (primary group) + whatever other group (secondary groups)
        # check DB contents
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 5
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == (
            users_count + 2 + 1
        )  # user primary groups, other groups, all group
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count + users_count)

        # change group name
        result = await conn.execute(
            groups.update()
            .where(groups.c.gid == quarrymen_group.gid)
            .values(name="The Beatles")
            .returning(literal_column("*"))
        )
        beatles_group = await result.fetchone()
        assert beatles_group.modified > quarrymen_group.modified

        # delete 1 user
        await conn.execute(users.delete().where(users.c.id == pete.id))

        # check DB contents
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 4
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == (users_count + 2 + 1)
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count + users_count)

        # add one user to another group
        await conn.execute(
            user_to_groups.insert().values(uid=ringo.id, gid=beatles_group.gid)
        )

        # check DB contents
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 4
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == (users_count + 2 + 1)
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count + 1 + users_count)

        # delete 1 group
        await conn.execute(groups.delete().where(groups.c.gid == rory_group.gid))

        # check DB contents
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 4
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == (users_count + 1 + 1)
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count + users_count)

        # delete the other group
        await conn.execute(groups.delete().where(groups.c.gid == beatles_group.gid))

        # check DB contents
        users_count = await conn.scalar(select([func.count()]).select_from(users))
        assert users_count == 4
        groups_count = await conn.scalar(select([func.count()]).select_from(groups))
        assert groups_count == (users_count + 0 + 1)
        relations_count = await conn.scalar(
            select([func.count()]).select_from(user_to_groups)
        )
        assert relations_count == (users_count + users_count)
