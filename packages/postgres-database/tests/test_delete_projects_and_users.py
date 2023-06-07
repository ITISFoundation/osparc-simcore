# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from psycopg2.errors import ForeignKeyViolation
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.webserver_models import projects, users
from sqlalchemy import func


@pytest.fixture
async def engine(pg_engine: Engine):
    async with pg_engine.acquire() as conn:
        await conn.execute(users.insert().values(**random_user(name="A")))
        await conn.execute(users.insert().values(**random_user()))
        await conn.execute(users.insert().values(**random_user()))

        await conn.execute(projects.insert().values(**random_project(prj_owner=1)))
        await conn.execute(projects.insert().values(**random_project(prj_owner=2)))
        await conn.execute(projects.insert().values(**random_project(prj_owner=3)))
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(projects.insert().values(**random_project(prj_owner=4)))

    yield pg_engine


@pytest.mark.skip(reason="sandbox for dev purposes")
async def test_insert_user(engine):
    async with engine.acquire() as conn:
        # execute + scalar
        res: ResultProxy = await conn.execute(
            users.insert().values(**random_user(name="FOO"))
        )
        assert res.returns_rows
        assert res.rowcount == 1
        assert res.keys() == ("id",)

        user_id = await res.scalar()
        assert isinstance(user_id, int)
        assert user_id > 0

        # only scalar
        user2_id: int = await conn.scalar(
            users.insert().values(**random_user(name="BAR"))
        )
        assert isinstance(user2_id, int)
        assert user2_id == user_id + 1

        # query result
        res: ResultProxy = await conn.execute(
            users.select().where(users.c.id == user2_id)
        )
        assert res.returns_rows
        assert res.rowcount == 1
        assert len(res.keys()) > 1

        # DIFFERENT betwen .first() and fetchone()

        user2: RowProxy = await res.first()
        # Fetch the first row and then close the result set unconditionally.
        assert res.closed

        res: ResultProxy = await conn.execute(
            users.select().where(users.c.id == user2_id)
        )
        user2a: RowProxy = await res.fetchone()
        # If rows are present, the cursor remains open after this is called.
        assert not res.closed
        assert user2 == user2a

        user2b: RowProxy = await res.fetchone()
        # If no more rows, the cursor is automatically closed and None is returned
        assert user2b is None
        assert res.closed


async def test_count_users(engine):
    async with engine.acquire() as conn:
        users_count = await conn.scalar(sa.select(func.count()).select_from(users))
        assert users_count == 3

        users_count = await conn.scalar(
            sa.select(sa.func.count()).where(users.c.name == "A")
        )
        assert users_count == 1

        users_count = await conn.scalar(
            sa.select(sa.func.count()).where(users.c.name == "UNKNOWN NAME")
        )
        assert users_count == 0


@pytest.mark.skip(reason="UNDER DEV")
async def test_view(engine):
    async with engine.acquire() as conn:
        async for row in conn.execute(users.select()):
            print(row)

        async for row in conn.execute(projects.select()):
            print(row)

        #
        await conn.execute(users.delete().where(users.c.name == "A"))

        res: ResultProxy = None
        rows: list[RowProxy] = []

        res = await conn.execute(users.select())
        rows = await res.fetchall()
        assert len(rows) == 2

        res = await conn.execute(projects.select())
        rows = await res.fetchall()
        assert len(rows) == 3
