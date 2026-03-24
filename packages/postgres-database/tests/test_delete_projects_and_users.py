# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import sqlalchemy as sa
import sqlalchemy.exc
from pytest_simcore.helpers.faker_factories import (
    random_product,
    random_project,
    random_user,
)
from simcore_postgres_database.webserver_models import products, projects, users
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def engine(asyncpg_engine: AsyncEngine):
    async with asyncpg_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        await conn.execute(users.insert().values(**random_user(name="A")))
        await conn.execute(users.insert().values(**random_user()))
        await conn.execute(users.insert().values(**random_user()))

        await conn.execute(products.insert().values(**random_product(name="test-product")))

        await conn.execute(projects.insert().values(**random_project(prj_owner=1, product_name="test-product")))
        await conn.execute(projects.insert().values(**random_project(prj_owner=2, product_name="test-product")))
        await conn.execute(projects.insert().values(**random_project(prj_owner=3, product_name="test-product")))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await conn.execute(projects.insert().values(**random_project(prj_owner=4)))

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await conn.execute(projects.insert().values(**random_project(prj_owner=1, product_name="unknown-product")))

    return asyncpg_engine


@pytest.mark.skip(reason="sandbox for dev purposes")
async def test_insert_user(engine: AsyncEngine):
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        # execute + scalar
        result = await conn.execute(users.insert().values(**random_user(name="FOO")))
        assert result.returns_rows
        assert result.rowcount == 1
        assert result.keys() == ("id",)

        user_id = result.scalars().one()
        assert isinstance(user_id, int)
        assert user_id > 0

        # only scalar
        user2_id = await conn.scalar(users.insert().values(**random_user(name="BAR")))
        assert isinstance(user2_id, int)
        assert user2_id == user_id + 1

        # query result
        result = await conn.execute(users.select().where(users.c.id == user2_id))
        assert result.returns_rows
        assert result.rowcount == 1
        assert len(result.keys()) > 1

        user2 = result.mappings().first()
        assert user2 is not None

        result = await conn.execute(users.select().where(users.c.id == user2_id))
        user2a = result.mappings().first()
        assert user2a is not None
        assert dict(user2) == dict(user2a)


async def test_count_users(engine: AsyncEngine):
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        users_count = await conn.scalar(sa.select(func.count()).select_from(users))
        assert users_count == 3

        users_count = await conn.scalar(sa.select(sa.func.count()).where(users.c.name == "A"))
        assert users_count == 1

        users_count = await conn.scalar(sa.select(sa.func.count()).where(users.c.name == "UNKNOWN NAME"))
        assert users_count == 0


@pytest.mark.skip(reason="UNDER DEV")
async def test_view(engine: AsyncEngine):
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        result = await conn.execute(users.select())
        for row in result.mappings():
            print(row)

        result = await conn.execute(projects.select())
        for row in result.mappings():
            print(row)

        await conn.execute(users.delete().where(users.c.name == "A"))

        result = await conn.execute(users.select())
        rows = result.mappings().all()
        assert len(rows) == 2

        result = await conn.execute(projects.select())
        rows = result.mappings().all()
        assert len(rows) == 3
