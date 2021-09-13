# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Optional

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users

USERNAME = f"{__name__}.me"
PARENT_PROJECT_NAME = f"{__name__}.parent"


@pytest.fixture
async def user(pg_engine: Engine) -> RowProxy:
    # some user
    async with pg_engine.acquire() as conn:
        result: Optional[ResultProxy] = await conn.execute(
            users.insert().values(**random_user(name=USERNAME)).returning(users)
        )
        assert result.rowcount == 1

        _user: Optional[RowProxy] = await result.first()
        assert _user
        assert _user.name == USERNAME
        return _user


@pytest.fixture
async def project(pg_engine: Engine, user: RowProxy) -> RowProxy:
    # a user's project
    async with pg_engine.acquire() as conn:
        result: Optional[ResultProxy] = await conn.execute(
            projects.insert()
            .values(**random_project(prj_owner=user.id, name=PARENT_PROJECT_NAME))
            .returning(projects)
        )
        assert result.rowcount == 1

        _project: Optional[RowProxy] = await result.first()
        assert _project
        assert _project.name == PARENT_PROJECT_NAME
        return _project


@pytest.fixture
async def conn(pg_engine: Engine) -> SAConnection:
    async with pg_engine.acquire() as conn:
        yield conn
