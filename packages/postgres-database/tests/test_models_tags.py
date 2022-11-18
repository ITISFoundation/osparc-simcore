from typing import Any, Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import UserRole, UserStatus, users


@pytest.fixture
async def setup_tables(
    pg_engine: Engine,
    create_fake_group: Callable[[SAConnection, Any], RowProxy],
    create_fake_user: Callable[[SAConnection, RowProxy, Any], RowProxy],
):
    # have some tags with user_id
    async with pg_engine.acquire() as conn:
        group = await create_fake_group(conn, name="some_group")
        user = await create_fake_user(
            conn,
            group=group,
            name="pcrespov",
            status=UserStatus.ACTIVE,
            role=UserRole.USER,
        )

        for data in [
            {"name": "tag1", "description": "description1", "color": "#f00"},
            {"name": "tag2", "description": "description2", "color": "#00f"},
        ]:
            await conn.scalar(
                tags.insert().values(user_id=user.id, **data).returning(tags.c.id)
            )


def foo():
    # we find group ids associated to this user

    j = user_to_groups.join(
        groups,
        (groups.c.gid == user_to_groups.c.gid) & (groups.c.type == GroupType.PRIMARY),
    )

    s = sa.select([user_to_groups.c.uid, user_to_groups.c.gid]).select_from(j)

    s = sa.select([tags.c.id, tags.c.name, user_to_groups.c.gid]).select_from(j)


def insert_():
    j = (
        tags.join(users)
        .join(user_to_groups)
        .join(
            groups,
            (groups.c.gid == user_to_groups.c.gid)
            & (groups.c.type == GroupType.PRIMARY),
        )
    )
    select_stmt = sa.select([tags.c.id, user_to_groups.c.gid]).select_from(j)
    insert_stmt = tags_to_groups.insert().from_select(
        [tags_to_groups.c.tag_id, tags_to_groups.c.group_id], select_stmt
    )

    update_stmt = tags_to_groups.update().values(write=True, delete=True)

    print(insert_stmt)
    print(update_stmt)
    print()


async def test_it3(pg_engine: Engine, setup_tables):

    async with pg_engine.acquire() as conn:

        await conn.execute(insert_stmt)

        # async for data in conn.execute():
        #     print(data)

        #     await conn.execute(
        #         tag_to_group.insert().values(
        #             tag_id=data["id"],
        #             group_id=data["gid"],
        #             read=True,
        #             write=True,
        #             delete=True,
        #         )
        #     )

    # transform them to a row in tag_to_group

    # def test_list_tags():
    # a tag in my group

    # a tag in another group

    # def test_update_tags():
    # a group in
