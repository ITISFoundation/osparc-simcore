# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Iterable
from uuid import UUID

import pytest
from aiopg.sa.engine import Engine
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.storage_models import projects, users
from simcore_service_storage.access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
)


@pytest.fixture
async def user_id(postgres_engine: Engine) -> Iterable[int]:
    # inject a random user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name="test")).returning(users.c.id)
    print(str(stmt))
    async with postgres_engine.acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.fetchone()

    assert isinstance(row.id, int)
    yield row.id

    async with postgres_engine.acquire() as conn:
        conn.execute(users.delete().where(users.c.id == row.id))


@pytest.fixture
async def project_id(user_id: int, postgres_engine: Engine) -> Iterable[UUID]:
    # inject a random project for user in db. This will give user_id, the full project's ownership

    # pylint: disable=no-value-for-parameter
    stmt = (
        projects.insert()
        .values(**random_project(prj_owner=user_id))
        .returning(projects.c.uuid)
    )
    print(str(stmt))
    async with postgres_engine.acquire() as conn:
        result = await conn.execute(stmt)
        [prj_uuid] = (await result.fetchone()).as_tuple()

    yield UUID(prj_uuid)

    async with postgres_engine.acquire() as conn:
        conn.execute(projects.delete().where(projects.c.uuid == prj_uuid))


@pytest.fixture
async def filemeta_id(
    user_id: int, project_id: str, postgres_engine: Engine
) -> Iterable[str]:
    raise NotImplementedError()


async def test_access_rights_on_owned_project(
    user_id: int, project_id: UUID, postgres_engine: Engine
):

    async with postgres_engine.acquire() as conn:

        access = await get_project_access_rights(conn, user_id, str(project_id))
        assert access == AccessRights.all()

        # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
        access = await get_file_access_rights(
            conn, user_id, f"{project_id}/node_id/not-in-file-metadata-table.txt"
        )
        assert access == AccessRights.all()
