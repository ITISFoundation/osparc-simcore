# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any, AsyncIterator, Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
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


async def test_it(
    pg_engine: Engine, user: RowProxy, group: RowProxy, other_user: RowProxy
):

    async with pg_engine.acquire() as conn:
        # have a repo
        tags_repo = TagsRepo(user_id=user.id)

        # create & own
        user_tags = [
            await tags_repo.create(conn, {"name": f"t{n}", "color": "blue"})
            for n in range(2)
        ]

        # repo has access
        for tag in user_tags:
            assert await tags_repo.access_count(conn, tag["id"], "read") == 1
            assert await tags_repo.access_count(conn, tag["id"], "write") == 1
            assert await tags_repo.access_count(conn, tag["id"], "delete") == 1

        # let's create a different repo for a different user i.e. other_user
        other_repo = TagsRepo(user_id=other_user.id)

        # other_user will have NO access to user's tags
        for tag in user_tags:
            assert await other_repo.access_count(conn, tag["id"], "read") == 0
            assert await other_repo.access_count(conn, tag["id"], "write") == 0
            assert await other_repo.access_count(conn, tag["id"], "delete") == 0


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
