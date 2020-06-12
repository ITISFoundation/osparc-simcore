# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import List
from uuid import uuid4

import faker
import pytest
import sqlalchemy as sa
from aiopg.sa.result import ResultProxy, RowProxy

from simcore_postgres_database.models.base import metadata
from psycopg2.errors import ForeignKeyViolation  # pylint: disable=no-name-in-module
from simcore_postgres_database.webserver_models import (
    UserStatus,
    projects,
    user_to_projects,
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


def random_project(**overrides):
    data = dict(
        uuid=uuid4(),
        name=fake.word(),
        description=fake.sentence(),
        prj_owner=fake.pyint(),
        access_rights={},
        workbench={},
        published=False,
    )
    data.update(overrides)
    return data


@pytest.fixture
def engine(make_engine, loop):
    async def start():
        engine = await make_engine()
        sync_engine = make_engine(False)
        metadata.drop_all(sync_engine)
        metadata.create_all(sync_engine)

        async with engine.acquire() as conn:
            await conn.execute(users.insert().values(**random_user(name="A")))
            await conn.execute(users.insert().values(**random_user()))
            await conn.execute(users.insert().values(**random_user()))

            await conn.execute(projects.insert().values(**random_project(prj_owner=1)))
            await conn.execute(projects.insert().values(**random_project(prj_owner=2)))
            await conn.execute(projects.insert().values(**random_project(prj_owner=3)))
            with pytest.raises(ForeignKeyViolation):
                await conn.execute(
                    projects.insert().values(**random_project(prj_owner=4))
                )

            await conn.execute(
                user_to_projects.insert().values(user_id=1, project_id=1)
            )
            await conn.execute(
                user_to_projects.insert().values(user_id=1, project_id=2)
            )
            await conn.execute(
                user_to_projects.insert().values(user_id=2, project_id=3)
            )

        return engine

    return loop.run_until_complete(start())


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
        users_count = await conn.scalar(users.count())
        assert users_count == 3

        users_count = await conn.scalar(
            sa.select([sa.func.count()]).where(users.c.name == "A")
        )
        assert users_count == 1

        users_count = await conn.scalar(
            sa.select([sa.func.count()]).where(users.c.name == "UNKNOWN NAME")
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
        rows: List[RowProxy] = []

        res = await conn.execute(users.select())
        rows = await res.fetchall()
        assert len(rows) == 2

        res = await conn.execute(projects.select())
        rows = await res.fetchall()
        assert len(rows) == 3

        # effect of cascade is that relation deletes as well
        res = await conn.execute(user_to_projects.select())
        rows = await res.fetchall()

        assert len(rows) == 1
        assert not any(row[user_to_projects.c.user_id] == 1 for row in rows)
