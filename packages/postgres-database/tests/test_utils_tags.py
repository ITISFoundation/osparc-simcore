# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any, Callable, Iterator

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_postgres_database.utils_tags import TagNotFoundError, TagsRepo


@pytest.fixture
async def connection(pg_engine: Engine) -> Iterator[SAConnection]:
    async with pg_engine.acquire() as _conn:
        yield _conn


@pytest.fixture
async def group(
    create_fake_group: Callable[[SAConnection, Any], RowProxy], connection: SAConnection
) -> RowProxy:
    group_ = await create_fake_group(connection)
    assert group_
    assert group_.type == "STANDARD"
    return group_


@pytest.fixture
async def user(
    create_fake_user: Callable[[SAConnection, RowProxy, Any], RowProxy],
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


async def test_tags_repo(pg_engine: Engine, user: RowProxy, group: RowProxy):

    async with pg_engine.acquire() as conn:
        repo = TagsRepo(user_id=user.id)

        # create & own
        tag1 = await repo.create(conn, {"name": "t1", "color": "blue"})
        tag2 = await repo.create(conn, {"name": "t2", "color": "red"})

        assert await repo.list_(conn) == [tag1, tag2]

        tag1_updated = {**tag1, **{"name": "new t1"}}

        assert (
            await repo.update(conn, tag_id=tag1["id"], tag_update={"name": "new t1"})
            == tag1_updated
        )

        assert await repo.get(conn, tag1["id"]) == tag1_updated

        await repo.delete(conn, tag1["id"])

        with pytest.raises(TagNotFoundError):
            await repo.get(conn, tag1["id"])
