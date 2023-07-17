# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from typing import AsyncIterable, Awaitable, Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.errors import ForeignKeyViolation, NotNullViolation
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import ClusterType, clusters
from simcore_postgres_database.models.users import users


@pytest.fixture(scope="function")
async def user_id(pg_engine: Engine) -> AsyncIterable[int]:
    async with pg_engine.acquire() as conn:
        # a 'me' user
        uid = await conn.scalar(
            users.insert().values(**(random_user())).returning(users.c.id)
        )
    assert uid is not None
    yield uid
    # cleanup
    async with pg_engine.acquire() as conn:
        # a 'me' user
        uid = await conn.execute(users.delete().where(users.c.id == uid))


@pytest.fixture
async def user_group_id(pg_engine: Engine, user_id: int) -> int:
    async with pg_engine.acquire() as conn:
        primary_gid = await conn.scalar(
            sa.select(users.c.primary_gid).where(users.c.id == user_id)
        )
    assert primary_gid is not None
    return primary_gid


async def test_cluster_without_owner_forbidden(
    create_fake_cluster: Callable[..., Awaitable[int]]
):
    with pytest.raises(NotNullViolation):
        await create_fake_cluster()


async def test_can_create_cluster_with_owner(
    user_group_id: int, create_fake_cluster: Callable[..., Awaitable[int]]
):
    aws_cluster_id = await create_fake_cluster(
        name="test AWS cluster", type=ClusterType.AWS, owner=user_group_id
    )
    assert aws_cluster_id > 0
    on_premise_cluster = await create_fake_cluster(
        name="test on premise cluster",
        type=ClusterType.ON_PREMISE,
        owner=user_group_id,
    )
    assert on_premise_cluster > 0
    assert on_premise_cluster != aws_cluster_id


async def test_cannot_remove_owner_that_owns_cluster(
    pg_engine: Engine,
    user_id: int,
    user_group_id: int,
    create_fake_cluster: Callable[..., Awaitable[int]],
):
    cluster_id = await create_fake_cluster(owner=user_group_id)
    # now try removing the user
    async with pg_engine.acquire() as conn:
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(users.delete().where(users.c.id == user_id))

    # now remove the cluster
    async with pg_engine.acquire() as conn:
        await conn.execute(clusters.delete().where(clusters.c.id == cluster_id))

    # removing the user should work now
    async with pg_engine.acquire() as conn:
        await conn.execute(users.delete().where(users.c.id == user_id))


async def test_cluster_owner_has_all_rights(
    pg_engine: Engine,
    user_group_id: int,
    create_fake_cluster: Callable[..., Awaitable[int]],
):
    cluster_id = await create_fake_cluster(owner=user_group_id)

    async with pg_engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            cluster_to_groups.select().where(
                cluster_to_groups.c.cluster_id == cluster_id
            )
        )

        assert result.rowcount == 1
        row = await result.fetchone()
        assert row is not None

        assert row.read is True
        assert row.write is True
        assert row.delete is True
