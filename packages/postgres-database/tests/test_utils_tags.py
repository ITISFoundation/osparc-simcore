# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any, AsyncIterator, Awaitable, Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowed,
    TagsRepo,
)


@pytest.fixture
async def connection(pg_engine: Engine) -> AsyncIterator[SAConnection]:
    async with pg_engine.acquire() as _conn:
        yield _conn


@pytest.fixture
async def group(
    create_fake_group: Callable[[SAConnection], Awaitable[RowProxy]],
    connection: SAConnection,
) -> RowProxy:
    group_ = await create_fake_group(connection)
    assert group_
    assert group_.type == "STANDARD"
    return group_


@pytest.fixture
async def user(
    create_fake_user: Callable[[SAConnection, RowProxy, Any], Awaitable[RowProxy]],
    group: RowProxy,
    connection: SAConnection,
) -> RowProxy:
    user_ = await create_fake_user(
        connection,
        group=group,
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )

    # note that this user belongs to two groups!
    assert user_.primary_gid != group.gid

    return user_


@pytest.fixture
async def other_user(
    create_fake_user: Callable[[SAConnection, RowProxy, Any], RowProxy],
    connection: SAConnection,
) -> RowProxy:
    user_ = await create_fake_user(
        connection,
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )
    return user_


async def test_tags_access_with_primary_groups(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection

    # have a repo
    tags_repo = TagsRepo(user_id=user.id)

    # create & own tag
    user_tags = [
        await tags_repo.create(conn, name=f"t{n}", color="blue") for n in range(2)
    ]

    # repo has access
    for tag in user_tags:
        assert await tags_repo.access_count(conn, tag["id"], read=True) == 1
        assert await tags_repo.access_count(conn, tag["id"], write=True) == 1
        assert await tags_repo.access_count(conn, tag["id"], delete=True) == 1

    # let's create a different repo for a different user i.e. other_user
    other_repo = TagsRepo(user_id=other_user.id)

    # other_user will have NO access to user's tags
    for tag in user_tags:
        assert await other_repo.access_count(conn, tag["id"], read=True) == 0
        assert await other_repo.access_count(conn, tag["id"], write=True) == 0
        assert await other_repo.access_count(conn, tag["id"], delete=True) == 0


async def create_tag(
    conn: SAConnection,
    *,
    name,
    description,
    color,
    group_id,
    read,
    write,
    delete,
) -> int:
    """helper to create a tab by inserting  rows in two different tables"""
    tag_id = await conn.scalar(
        tags.insert()
        .values(name=name, description=description, color=color)
        .returning(tags.c.id)
    )
    assert tag_id
    await conn.execute(
        tags_to_groups.insert().values(
            tag_id=tag_id, group_id=group_id, read=read, write=write, delete=delete
        )
    )
    return tag_id


async def test_tags_access_with_standard_groups(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection

    # insert a tag and give RW access to a group
    tag_id = await create_tag(
        conn,
        name="G1",
        description=f"Tag of group {group['type']}",
        color="black",
        group_id=group.gid,
        read=True,
        write=True,
        delete=False,
    )

    # user is part of this group
    tags_repo = TagsRepo(user_id=user.id)
    assert await tags_repo.access_count(conn, tag_id, read=True) == 1
    assert await tags_repo.access_count(conn, tag_id, write=True) == 1
    assert await tags_repo.access_count(conn, tag_id, delete=True) == 0

    # other_user is NOT part of this group
    other_repo = TagsRepo(user_id=other_user.id)
    assert await other_repo.access_count(conn, tag_id, read=True) == 0
    assert await other_repo.access_count(conn, tag_id, write=True) == 0
    assert await other_repo.access_count(conn, tag_id, delete=True) == 0


async def test_tags_repo_list_and_get(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection
    tags_repo = TagsRepo(user_id=user.id)

    # (1) no tags
    listed_tags = await tags_repo.list(conn)
    assert not listed_tags

    # (2) one tag
    expected_tags_ids = [
        await create_tag(
            conn,
            name="T1",
            description=f"tag for {user.id}",
            color="blue",
            group_id=user.primary_gid,
            read=True,
            write=False,
            delete=False,
        )
    ]

    listed_tags = await tags_repo.list(conn)
    assert listed_tags
    assert [t["id"] for t in listed_tags] == expected_tags_ids

    # (3) another tag via its standard group
    expected_tags_ids.append(
        await create_tag(
            conn,
            name="T2",
            description="tag via std group",
            color="red",
            group_id=group.gid,
            read=True,
            write=False,
            delete=False,
        )
    )

    listed_tags = await tags_repo.list(conn)
    assert {t["id"] for t in listed_tags} == set(expected_tags_ids)

    # (4) add another tag from a differnt user
    await create_tag(
        conn,
        name="T3",
        description=f"tag for {other_user.id}",
        color="green",
        group_id=other_user.primary_gid,
        read=True,
        write=False,
        delete=False,
    )

    # same as before
    prev_listed_tags = listed_tags
    listed_tags = await tags_repo.list(conn)
    assert listed_tags == prev_listed_tags

    # (5) add a global tag
    tag_id = await create_tag(
        conn,
        name="TG",
        description="tag for EVERYBODY",
        color="pink",
        group_id=1,
        read=True,
        write=False,
        delete=False,
    )

    listed_tags = await tags_repo.list(conn)
    assert listed_tags == [
        {"id": 1, "name": "T1", "description": "tag for 1", "color": "blue"},
        {"id": 2, "name": "T2", "description": "tag via std group", "color": "red"},
        {"id": 4, "name": "TG", "description": "tag for EVERYBODY", "color": "pink"},
    ]

    other_repo = TagsRepo(user_id=other_user.id)
    assert await other_repo.list(conn) == [
        {"id": 3, "name": "T3", "description": "tag for 2", "color": "green"},
        {"id": 4, "name": "TG", "description": "tag for EVERYBODY", "color": "pink"},
    ]

    # exclusive to user
    assert await tags_repo.get(conn, tag_id=2) == {
        "id": 2,
        "name": "T2",
        "description": "tag via std group",
        "color": "red",
    }

    # exclusive ot other user
    with pytest.raises(TagNotFoundError):
        assert await tags_repo.get(conn, tag_id=3)

    assert await other_repo.get(conn, tag_id=3) == {
        "id": 3,
        "name": "T3",
        "description": "tag for 2",
        "color": "green",
    }

    # a common tag
    assert await tags_repo.get(conn, tag_id=4) == await other_repo.get(conn, tag_id=4)


async def test_tags_repo_update(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection
    tags_repo = TagsRepo(user_id=user.id)

    # Tags with different access rights
    readonly_tid, readwrite_tid, other_tid = [
        await create_tag(
            conn,
            name="T1",
            description="read only",
            color="blue",
            group_id=user.primary_gid,
            read=True,
            write=False,  # <--- read only
            delete=False,
        ),
        await create_tag(
            conn,
            name="T2",
            description="read/write",
            color="green",
            group_id=user.primary_gid,
            read=True,
            write=True,  # <--- can write
            delete=False,
        ),
        await create_tag(
            conn,
            name="T3",
            description="read/write but a other user",
            color="blue",
            group_id=other_user.primary_gid,
            read=True,
            write=True,  # <--- can write but other user
            delete=False,
        ),
    ]

    with pytest.raises(TagOperationNotAllowed):
        await tags_repo.update(conn, tag_id=readonly_tid, description="modified")

    assert await tags_repo.update(
        conn, tag_id=readwrite_tid, description="modified"
    ) == {
        "id": readwrite_tid,
        "name": "T2",
        "description": "modified",
        "color": "green",
    }

    with pytest.raises(TagOperationNotAllowed):
        await tags_repo.update(conn, tag_id=other_tid, description="modified")


async def test_tags_repo_delete(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection
    tags_repo = TagsRepo(user_id=user.id)

    # Tags with different access rights
    readonly_tid, delete_tid, other_tid = [
        await create_tag(
            conn,
            name="T1",
            description="read only",
            color="blue",
            group_id=user.primary_gid,
            read=True,
            write=False,  # <--- read only
            delete=False,
        ),
        await create_tag(
            conn,
            name="T2",
            description="read/write",
            color="green",
            group_id=user.primary_gid,
            read=True,
            write=True,
            delete=True,  # <-- can delete
        ),
        await create_tag(
            conn,
            name="T3",
            description="read/write but a other user",
            color="blue",
            group_id=other_user.primary_gid,
            read=True,
            write=True,
            delete=True,  # <-- can delete but other user
        ),
    ]

    # cannot delete
    with pytest.raises(TagOperationNotAllowed):
        await tags_repo.delete(conn, tag_id=readonly_tid)

    # can delete
    await tags_repo.get(conn, tag_id=delete_tid)
    await tags_repo.delete(conn, tag_id=delete_tid)

    with pytest.raises(TagNotFoundError):
        await tags_repo.get(conn, tag_id=delete_tid)

    # cannot delete
    with pytest.raises(TagOperationNotAllowed):
        await tags_repo.delete(conn, tag_id=other_tid)


async def test_tags_repo_create(
    connection: SAConnection, user: RowProxy, group: RowProxy, other_user: RowProxy
):
    conn = connection
    tags_repo = TagsRepo(user_id=user.id)

    tag_1 = await tags_repo.create(
        conn,
        name="T1",
        description="my first tag",
        color="pink",
        read=True,
        write=True,
        delete=True,
    )
    assert tag_1 == {
        "id": 1,
        "name": "T1",
        "description": "my first tag",
        "color": "pink",
    }

    # assigned primary group
    assert (
        await conn.scalar(
            sa.select([tags_to_groups.c.group_id]).where(
                tags_to_groups.c.tag_id == tag_1["id"]
            )
        )
        == user.primary_gid
    )


@pytest.mark.skip(reason="DEV")
async def test_tags_repo_workflow(
    pg_engine: Engine, user: RowProxy, group: RowProxy, other_user: RowProxy
):

    async with pg_engine.acquire() as conn:
        my_tags_repo = TagsRepo(user_id=user.id)

        # create & own
        tag1 = await my_tags_repo.create(conn, {"name": "t1", "color": "blue"})
        tag2a = await my_tags_repo.create(conn, {"name": "t2", "color": "red"})
        tag2b = await my_tags_repo.create(conn, {"name": "t2", "color": "red"})

        assert tag2a != tag2b  #  different ids!

        for tag in [tag1, tag2a, tag2b]:
            for access in ("read", "write", "delete"):
                assert await my_tags_repo.access_count(
                    conn, tag_id=tag["id"], access=access
                )

        # list
        assert await my_tags_repo.list(conn) == [tag1, tag2a, tag2b]

        tag1_updated = {**tag1, **{"name": "new t1"}}

        assert (
            await my_tags_repo.update(
                conn, tag_id=tag1["id"], tag_update={"name": "new t1"}
            )
            == tag1_updated
        )

        assert await my_tags_repo.get(conn, tag1["id"]) == tag1_updated

        await my_tags_repo.delete(conn, tag1["id"])

        with pytest.raises(TagNotFoundError):
            await my_tags_repo.get(conn, tag1["id"])

        # new user
        other_tags_repo = TagsRepo(user_id=other_user.id)

        # create & own tags
        tag3 = await other_tags_repo.create(conn, {"name": "t3", "color": "brown"})
        assert await other_tags_repo.get(conn, tag3["id"]) == tag3

        # but cannot access to other's tags
        assert await my_tags_repo.get(conn, tag2a["id"]) == tag2a

        with pytest.raises(TagNotFoundError):
            await other_tags_repo.get(conn, tag2a["id"])

        with pytest.raises(TagOperationNotAllowed):
            await other_tags_repo.delete(conn, tag2a["id"])

        with pytest.raises(TagOperationNotAllowed):
            await other_tags_repo.update(conn, tag2a["id"], {"name": "fooooo"})

        assert await other_tags_repo.list(conn)
