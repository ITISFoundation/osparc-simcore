# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections import namedtuple
from uuid import UUID

import aiopg.sa
import pytest
import sqlalchemy as sa
from aiohttp.test_utils import make_mocked_request
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.snapshots import snapshots
from simcore_postgres_database.models.users import users
from simcore_service_webserver.constants import APP_DB_ENGINE_KEY, RQT_USERID_KEY
from simcore_service_webserver.snapshots_db import SnapshotsRepository

USERNAME = "me"
PARENT_PROJECT_NAME = "parent"
PROJECT_UUID = "322d8808-cca7-4cc4-9a17-ac79a080e721"


@pytest.fixture
async def engine(loop, postgres_db: sa.engine.Engine):
    # pylint: disable=no-value-for-parameter

    async with aiopg.sa.create_engine(str(postgres_db.url)) as pg_engine:
        # injects TABLES ...
        async with pg_engine.acquire() as conn:
            # a 'me' user
            user_id = await conn.scalar(
                users.insert()
                .values(**random_user(name=USERNAME))
                .returning(users.c.id)
            )
            # has a project 'parent'
            await conn.execute(
                projects.insert().values(
                    **random_project(
                        prj_owner=user_id, name=PARENT_PROJECT_NAME, uuid=PROJECT_UUID
                    )
                )
            )
        yield pg_engine


@pytest.fixture
def snapshots_repo(engine):
    app = {}
    app[APP_DB_ENGINE_KEY] = engine

    request = make_mocked_request("GET", "/project/{PROJECT_UUID}/snapshots")
    request.app[APP_DB_ENGINE_KEY] = engine

    return SnapshotsRepository(request)


async def test_read_snapshots(snapshots_repo: SnapshotsRepository):

    assert not await snapshots_repo.list(project_uuid=UUID(PROJECT_UUID))
