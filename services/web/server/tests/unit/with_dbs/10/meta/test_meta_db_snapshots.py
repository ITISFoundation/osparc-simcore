# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime
from uuid import UUID

import aiopg.sa
import pytest
import sqlalchemy as sa
from aiohttp.test_utils import make_mocked_request
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_service_webserver.constants import APP_DB_ENGINE_KEY
from simcore_service_webserver.meta_db_snapshots import SnapshotsRepository
from simcore_service_webserver.meta_models_snapshots import Snapshot

USERNAME = "me"
PARENT_PROJECT_NAME = "parent"
PROJECT_UUID = "322d8808-cca7-4cc4-9a17-ac79a080e721"
ANOTHER_UUID = "d337b9a1-9e2b-4d6d-805e-351554d26d1f"


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
            # has a project 'another'
            await conn.execute(
                projects.insert().values(
                    **random_project(
                        prj_owner=user_id, name="another", uuid=ANOTHER_UUID
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


async def test_snapshot_repo(snapshots_repo: SnapshotsRepository, faker: Faker):

    assert not await snapshots_repo.list_all(project_uuid=UUID(PROJECT_UUID))

    snapshot = Snapshot(
        name="dummy",
        created_at=datetime.now(),
        parent_uuid=PROJECT_UUID,
        project_uuid=ANOTHER_UUID,
    )

    snapshot_orm = await snapshots_repo.create(snapshot)
    assert snapshot_orm.parent_uuid == PROJECT_UUID
