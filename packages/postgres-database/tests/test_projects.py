# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict

import pytest
from aiopg.sa.engine import Engine
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users

USERNAME = f"{__name__}.me"
PARENT_PROJECT_NAME = f"{__name__}.parent"


@pytest.fixture
async def user_id(pg_engine: Engine) -> int:
    # has a user
    async with pg_engine.acquire() as conn:
        _id = await conn.scalar(
            users.insert().values(**random_user(name=USERNAME)).returning(users.c.id)
        )
        assert _id is not None
        return _id


async def test_rawdata_fakers_random_project(pg_engine: Engine, user_id: int):
    # ensures pytest_simcore.helpers.rawdata_fakers.random_project is up-to-date

    fake_data: Dict[str, Any] = random_project(
        prj_owner=user_id, name=PARENT_PROJECT_NAME
    )
    async with pg_engine.acquire() as conn:
        pid = await conn.scalar(
            projects.insert().values(**fake_data).returning(projects.c.id)
        )
        assert pid is not None

        result = await conn.execute(projects.select().where(projects.c.id == pid))
        row = await result.first()

        assert row

        # columns inserted
        assert {key: row[key] for key in fake_data.keys()} == fake_data

        # columns created in pg server
        assert row.creation_date == row.last_change_date


async def test_it(pg_engine: Engine):
    # workbench
    pass
