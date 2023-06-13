# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Any, AsyncIterator, Awaitable, Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.storage_models import projects, users


@pytest.fixture
async def user_id(aiopg_engine: Engine) -> AsyncIterator[UserID]:
    # inject a random user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name="test")).returning(users.c.id)
    print(str(stmt))
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.fetchone()
    assert row
    assert isinstance(row.id, int)
    yield row.id

    async with aiopg_engine.acquire() as conn:
        await conn.execute(users.delete().where(users.c.id == row.id))


@pytest.fixture
async def create_project(
    user_id: UserID, aiopg_engine: Engine
) -> AsyncIterator[Callable[[], Awaitable[dict[str, Any]]]]:
    created_project_uuids = []

    async def _creator(**kwargs) -> dict[str, Any]:
        prj_config = {"prj_owner": user_id}
        prj_config.update(kwargs)
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                projects.insert()
                .values(**random_project(**prj_config))
                .returning(sa.literal_column("*"))
            )
            row = await result.fetchone()
            assert row
            created_project_uuids.append(row[projects.c.uuid])
            return dict(row)

    yield _creator
    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_uuids))
        )


@pytest.fixture
async def project_id(
    create_project: Callable[[], Awaitable[dict[str, Any]]]
) -> ProjectID:
    project = await create_project()
    return ProjectID(project["uuid"])


@pytest.fixture
async def create_project_node(
    user_id: UserID, aiopg_engine: Engine, faker: Faker
) -> AsyncIterator[Callable[..., Awaitable[NodeID]]]:
    async def _creator(
        project_id: ProjectID, node_id: NodeID | None = None, **kwargs
    ) -> NodeID:
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                sa.select(projects.c.workbench).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            row = await result.fetchone()
            assert row
            project_workbench: dict[str, Any] = row[projects.c.workbench]
            new_node_id = node_id or NodeID(faker.uuid4())
            node_data = {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "pytest_fake_node",
            }
            node_data.update(**kwargs)
            project_workbench.update({f"{new_node_id}": node_data})
            await conn.execute(
                projects.update()
                .where(projects.c.uuid == f"{project_id}")
                .values(workbench=project_workbench)
            )
        return new_node_id

    yield _creator
