# pylint: disable=E1120

import faker
import pytest
import sqlalchemy as sa
from aiopg.sa.result import ResultProxy, RowProxy
from psycopg2.errors import ForeignKeyViolation, RaiseException, UniqueViolation
from sqlalchemy import literal_column

from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import (
    GroupType,
    UserStatus,
    groups,
    user_to_groups,
    users,
)

fake = faker.Faker()


def random_user(**overrides):
    data = dict(
        name=fake.name(),
        email=fake.email(),
        password_hash=fake.numerify(text="#" * 5),
        status=UserStatus.ACTIVE,
        created_ip=fake.ipv4(),
    )
    data.update(overrides)
    return data


def random_group(**overrides):
    data = dict(name=fake.company(), description=fake.text(), type="STANDARD")
    data.update(overrides)
    return data


async def _create_group(conn, **overrides) -> RowProxy:
    result = await conn.execute(
        groups.insert()
        .values(**random_group(**overrides))
        .returning(literal_column("*"))
    )
    return await result.fetchone()


async def _create_user(conn, name: str, group: RowProxy) -> RowProxy:
    result = await conn.execute(
        users.insert().values(**random_user(name=name)).returning(literal_column("*"))
    )
    user = await result.fetchone()
    result = await conn.execute(
        user_to_groups.insert().values(uid=user.id, gid=group.gid)
    )
    return user


async def test_user_group_uniqueness(make_engine):
    engine = await make_engine()
    sync_engine = make_engine(False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        rory_group = await _create_group(conn, name="Rory Storm and the Hurricanes")
        ringo = await _create_user(conn, "Ringo", rory_group)
        # test unique user/group pair
        with pytest.raises(UniqueViolation, match="user_to_groups_uid_gid_key"):
            await conn.execute(
                user_to_groups.insert().values(uid=ringo.id, gid=rory_group.gid)
            )

async def test_all_group(make_engine):
    engine = await make_engine()
    sync_engine = make_engine(False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        # now check the only available group is the all group
        groups_count = await conn.scalar(
            groups.count()
        )
        assert groups_count == 1

        result = await conn.execute(
            groups.select().where(groups.c.type == GroupType.EVERYONE)
        )
        all_group_gid = (await result.fetchone()).gid
        assert all_group_gid == 1 # it's the first group so it gets a 1
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
        users_count = await conn.scalar(users.count())
        assert users_count == 0

        # check the all group still exists
        groups_count = await conn.scalar(
            groups.count()
        )
        assert groups_count == 1
        result = await conn.execute(
            groups.select().where(groups.c.type == GroupType.EVERYONE)
        )
        all_group_gid = (await result.fetchone()).gid
        assert all_group_gid == 1 # it's the first group so it gets a 1



async def test_own_group(make_engine):
    engine = await make_engine()
    sync_engine = make_engine(False)
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
            groups.count().where(groups.c.gid == user.primary_gid)
        )
        assert groups_count == 1

        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == 2 # own group + all group

        # try removing the primary group
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(groups.delete().where(groups.c.gid == user.primary_gid))

        # now remove the users should remove the primary group
        await conn.execute(users.delete().where(users.c.id == user.id))
        users_count = await conn.scalar(users.count())
        assert users_count == 0
        groups_count = await conn.scalar(groups.count())
        assert groups_count == 1 # the all group is still around
        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == (users_count + users_count)


async def test_group(make_engine):
    engine = await make_engine()
    sync_engine = make_engine(False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)
    async with engine.acquire() as conn:
        rory_group = await _create_group(conn, name="Rory Storm and the Hurricanes")
        quarrymen_group = await _create_group(conn, name="The Quarrymen")
        await _create_user(conn, "John", quarrymen_group)
        await _create_user(conn, "Paul", quarrymen_group)
        await _create_user(conn, "Georges", quarrymen_group)
        pete = await _create_user(conn, "Pete", quarrymen_group)
        ringo = await _create_user(conn, "Ringo", rory_group)

        # rationale: following linux user/group system, each user has its own group (primary group) + whatever other group (secondary groups)
        # check DB contents
        users_count = await conn.scalar(users.count())
        assert users_count == 5
        groups_count = await conn.scalar(groups.count())
        assert groups_count == (users_count + 2 + 1) # user primary groups, other groups, all group
        relations_count = await conn.scalar(user_to_groups.count())
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
        users_count = await conn.scalar(users.count())
        assert users_count == 4
        groups_count = await conn.scalar(groups.count())
        assert groups_count == (users_count + 2 + 1)
        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == (users_count + users_count + users_count)

        # add one user to another group
        await conn.execute(
            user_to_groups.insert().values(uid=ringo.id, gid=beatles_group.gid)
        )

        # check DB contents
        users_count = await conn.scalar(users.count())
        assert users_count == 4
        groups_count = await conn.scalar(groups.count())
        assert groups_count == (users_count + 2 + 1)
        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == (users_count + users_count + 1 + users_count)

        # delete 1 group
        await conn.execute(groups.delete().where(groups.c.gid == rory_group.gid))

        # check DB contents
        users_count = await conn.scalar(users.count())
        assert users_count == 4
        groups_count = await conn.scalar(groups.count())
        assert groups_count == (users_count + 1 + 1)
        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == (users_count + users_count + users_count)

        # delete the other group
        await conn.execute(groups.delete().where(groups.c.gid == beatles_group.gid))

        # check DB contents
        users_count = await conn.scalar(users.count())
        assert users_count == 4
        groups_count = await conn.scalar(groups.count())
        assert groups_count == (users_count + 0 + 1)
        relations_count = await conn.scalar(user_to_groups.count())
        assert relations_count == (users_count + users_count)
