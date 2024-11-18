# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pytest_simcore.helpers.postgres_tags import create_tag, create_tag_access
from simcore_postgres_database.models.tags_access_rights import tags_access_rights
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowedError,
    TagsRepo,
)
from simcore_postgres_database.utils_tags_sql import (
    add_tag_to_project_stmt,
    add_tag_to_services_stmt,
    create_tag_stmt,
    delete_tag_stmt,
    get_tag_stmt,
    get_tags_for_project_stmt,
    get_tags_for_services_stmt,
    list_tags_stmt,
    set_tag_access_rights_stmt,
    update_tag_stmt,
)
from sqlalchemy.ext.asyncio import AsyncEngine


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
    return await create_fake_user(
        connection,
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )


async def test_tags_access_with_primary_groups(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):
    conn = connection

    (tag_id, other_tag_id) = [
        await create_tag(
            conn,
            name="T1",
            description="tag 1",
            color="blue",
            group_id=user.primary_gid,
            read=True,
            write=True,
            delete=True,
        ),
        await create_tag(
            conn,
            name="T2",
            description="tag for other_user",
            color="yellow",
            group_id=other_user.primary_gid,
            read=True,
            write=True,
            delete=True,
        ),
    ]

    tags_repo = TagsRepo(asyncpg_engine)

    # repo has access
    assert (
        await tags_repo.access_count(
            user_id=user.id, tag_id=tag_id, read=True, write=True, delete=True
        )
        == 1
    )
    assert (
        await tags_repo.access_count(
            user_id=user.id, tag_id=tag_id, read=True, write=True
        )
        == 1
    )
    assert await tags_repo.access_count(user_id=user.id, tag_id=tag_id, read=True) == 1
    assert await tags_repo.access_count(user_id=user.id, tag_id=tag_id, write=True) == 1

    # changing access conditions
    assert (
        await tags_repo.access_count(
            user_id=user.id,
            tag_id=tag_id,
            read=True,
            write=True,
            delete=False,  # <---
        )
        == 0
    )

    # user will have NO access to other user's tags even matching access rights
    assert (
        await tags_repo.access_count(
            user_id=user.id, tag_id=other_tag_id, read=True, write=True, delete=True
        )
        == 0
    )


async def test_tags_access_with_multiple_groups(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):

    conn = connection

    (tag_id, other_tag_id, group_tag_id, everyone_tag_id) = [
        await create_tag(
            conn,
            name="T1",
            description="tag 1",
            color="blue",
            group_id=user.primary_gid,
            read=True,
            write=True,
            delete=True,
        ),
        await create_tag(
            conn,
            name="T2",
            description="tag for other_user",
            color="yellow",
            group_id=other_user.primary_gid,
            read=True,
            write=True,
            delete=True,
        ),
        await create_tag(
            conn,
            name="TG",
            description="read-write tag shared in a GROUP ( currently only user)",
            color="read",
            group_id=group.gid,
            read=True,
            write=True,
            delete=False,
        ),
        await create_tag(
            conn,
            name="TE",
            description="read-only tag shared with EVERYONE",
            color="pink",
            group_id=1,
            read=True,
            write=False,
            delete=False,
        ),
    ]

    tags_repo = TagsRepo(asyncpg_engine)
    other_repo = TagsRepo(asyncpg_engine)

    # tag_id
    assert (
        await tags_repo.access_count(
            user_id=user.id, tag_id=tag_id, read=True, write=True, delete=True
        )
        == 1
    )
    assert (
        await other_repo.access_count(
            user_id=other_user.id, tag_id=tag_id, read=True, write=True, delete=True
        )
        == 0
    )

    # other_tag_id
    assert (
        await tags_repo.access_count(user_id=user.id, tag_id=other_tag_id, read=True)
        == 0
    )
    assert (
        await other_repo.access_count(
            user_id=other_user.id, tag_id=other_tag_id, read=True
        )
        == 1
    )

    # group_tag_id
    assert (
        await tags_repo.access_count(user_id=user.id, tag_id=group_tag_id, read=True)
        == 1
    )
    assert (
        await other_repo.access_count(
            user_id=other_user.id, tag_id=group_tag_id, read=True
        )
        == 0
    )

    # everyone_tag_id
    assert (
        await tags_repo.access_count(user_id=user.id, tag_id=everyone_tag_id, read=True)
        == 1
    )
    assert (
        await other_repo.access_count(
            user_id=other_user.id, tag_id=everyone_tag_id, read=True
        )
        == 1
    )

    # now group adds read for all tags
    for t in (tag_id, other_tag_id, everyone_tag_id):
        await create_tag_access(
            conn,
            group_id=group.gid,
            tag_id=t,
            read=True,
            write=False,
            delete=False,
        )

    assert await tags_repo.access_count(user_id=user.id, tag_id=tag_id, read=True) == 2
    assert (
        await tags_repo.access_count(user_id=user.id, tag_id=other_tag_id, read=True)
        == 1
    )
    assert (
        await tags_repo.access_count(user_id=user.id, tag_id=everyone_tag_id, read=True)
        == 2
    )


async def test_tags_repo_list_and_get(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):
    conn = connection
    tags_repo = TagsRepo(asyncpg_engine)

    # (1) no tags
    listed_tags = await tags_repo.list_all(user_id=user.id)
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

    listed_tags = await tags_repo.list_all(user_id=user.id)
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

    listed_tags = await tags_repo.list_all(user_id=user.id)
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
    listed_tags = await tags_repo.list_all(user_id=user.id)
    assert listed_tags == prev_listed_tags

    # (5) add a global tag
    await create_tag(
        conn,
        name="TG",
        description="tag for EVERYBODY",
        color="pink",
        group_id=1,
        read=True,
        write=False,
        delete=False,
    )

    listed_tags = await tags_repo.list_all(user_id=user.id)
    assert listed_tags == [
        {
            "id": 1,
            "name": "T1",
            "description": "tag for 1",
            "color": "blue",
            "read": True,
            "write": False,
            "delete": False,
        },
        {
            "id": 2,
            "name": "T2",
            "description": "tag via std group",
            "color": "red",
            "read": True,
            "write": False,
            "delete": False,
        },
        {
            "id": 4,
            "name": "TG",
            "description": "tag for EVERYBODY",
            "color": "pink",
            "read": True,
            "write": False,
            "delete": False,
        },
    ]

    other_repo = TagsRepo(asyncpg_engine)
    assert await other_repo.list_all(user_id=other_user.id) == [
        {
            "id": 3,
            "name": "T3",
            "description": "tag for 2",
            "color": "green",
            "read": True,
            "write": False,
            "delete": False,
        },
        {
            "id": 4,
            "name": "TG",
            "description": "tag for EVERYBODY",
            "color": "pink",
            "read": True,
            "write": False,
            "delete": False,
        },
    ]

    # exclusive to user
    assert await tags_repo.get(user_id=user.id, tag_id=2) == {
        "id": 2,
        "name": "T2",
        "description": "tag via std group",
        "color": "red",
        "read": True,
        "write": False,
        "delete": False,
    }

    # exclusive ot other user
    with pytest.raises(TagNotFoundError):
        assert await tags_repo.get(user_id=user.id, tag_id=3)

    assert await other_repo.get(user_id=other_user.id, tag_id=3) == {
        "id": 3,
        "name": "T3",
        "description": "tag for 2",
        "color": "green",
        "read": True,
        "write": False,
        "delete": False,
    }

    # a common tag
    assert await tags_repo.get(user_id=user.id, tag_id=4) == await other_repo.get(
        user_id=user.id, tag_id=4
    )


async def test_tags_repo_uniquely_list_or_get_shared_tags(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
):
    conn = connection
    tags_repo = TagsRepo(asyncpg_engine)

    # (1) create a tag which cannot be written
    expected_tag_id = await create_tag(
        conn,
        name="T1",
        description=f"tag for {user.id}",
        color="blue",
        group_id=user.primary_gid,
        read=True,
        write=False,  # <-- cannot write
        delete=True,
    )

    got = await tags_repo.get(user_id=user.id, tag_id=expected_tag_id)
    assert got
    assert got["id"] == expected_tag_id
    assert got["read"] is True
    assert got["write"] is False  # <--
    assert got["delete"] is True

    # (2) share with standard group
    await create_tag_access(
        conn,
        tag_id=expected_tag_id,
        group_id=group.gid,
        read=True,
        write=True,  # < -- group can write
        delete=False,
    )

    # checks that the agregattion is the MOST permisive
    # checks that user_id has now full access via its primary and its stadard group
    got = await tags_repo.get(user_id=user.id, tag_id=expected_tag_id)
    assert got
    assert got["id"] == expected_tag_id
    assert got["read"] is True
    assert got["write"] is True  # <--
    assert got["delete"] is True

    user_tags = await tags_repo.list_all(user_id=user.id)
    assert user_tags == [got]


async def test_tags_repo_update(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):
    conn = connection
    tags_repo = TagsRepo(asyncpg_engine)

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

    with pytest.raises(TagOperationNotAllowedError):
        await tags_repo.update(
            user_id=user.id, tag_id=readonly_tid, description="modified"
        )

    assert await tags_repo.update(
        user_id=user.id, tag_id=readwrite_tid, description="modified"
    ) == {
        "id": readwrite_tid,
        "name": "T2",
        "description": "modified",
        "color": "green",
        "read": True,
        "write": True,  # <--- can write
        "delete": False,
    }

    with pytest.raises(TagOperationNotAllowedError):
        await tags_repo.update(
            user_id=user.id, tag_id=other_tid, description="modified"
        )


async def test_tags_repo_delete(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):
    conn = connection
    tags_repo = TagsRepo(asyncpg_engine)

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
    with pytest.raises(TagOperationNotAllowedError):
        await tags_repo.delete(user_id=user.id, tag_id=readonly_tid)

    # can delete
    await tags_repo.get(user_id=user.id, tag_id=delete_tid)
    await tags_repo.delete(user_id=user.id, tag_id=delete_tid)

    with pytest.raises(TagNotFoundError):
        await tags_repo.get(user_id=user.id, tag_id=delete_tid)

    # cannot delete
    with pytest.raises(TagOperationNotAllowedError):
        await tags_repo.delete(user_id=user.id, tag_id=other_tid)


async def test_tags_repo_create(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    user: RowProxy,
    group: RowProxy,
    other_user: RowProxy,
):
    conn = connection
    tags_repo = TagsRepo(asyncpg_engine)

    tag_1 = await tags_repo.create(
        user_id=user.id,
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
        "read": True,
        "write": True,
        "delete": True,
    }

    # assigned primary group
    assert (
        await conn.scalar(
            sa.select(tags_access_rights.c.group_id).where(
                tags_access_rights.c.tag_id == tag_1["id"]
            )
        )
        == user.primary_gid
    )


def test_building_tags_sql_statements():
    def _check(func_smt, **kwargs):
        print(f"{func_smt.__name__:*^100}")
        stmt = func_smt(**kwargs)
        print()
        print(as_postgres_sql_query_str(stmt))
        print()

    # some data
    product_name = "osparc"
    user_id = 425  # 4
    tag_id = 4
    project_index = 1
    project_uuid = "106f8b4b-ffb6-459a-a27b-981c779e6d3f"
    service_key = "simcore/services/comp/isolve"
    service_version = "2.0.85"

    _check(
        list_tags_stmt,
        user_id=user_id,
    )

    _check(
        get_tag_stmt,
        user_id=user_id,
        tag_id=tag_id,
    )

    _check(
        create_tag_stmt,
        name="foo",
        description="description",
    )

    _check(
        set_tag_access_rights_stmt,
        tag_id=tag_id,
        user_id=user_id,
        read=True,
        write=True,
        delete=True,
    )

    _check(
        update_tag_stmt,
        user_id=user_id,
        tag_id=tag_id,
        # updates
        name="foo",
    )

    _check(
        delete_tag_stmt,
        user_id=user_id,
        tag_id=tag_id,
    )

    _check(
        get_tags_for_project_stmt,
        project_index=project_index,
    )

    _check(
        get_tags_for_services_stmt,
        key=service_key,
        version=service_version,
    )

    _check(
        add_tag_to_project_stmt,
        project_index=project_index,
        tag_id=tag_id,
        project_uuid_for_rut=project_uuid,
    )

    _check(
        add_tag_to_services_stmt,
        key=service_key,
        version=service_version,
        tag_id=tag_id,
    )
