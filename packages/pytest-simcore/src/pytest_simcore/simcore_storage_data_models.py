# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.storage_models import projects, users
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .helpers.faker_factories import DEFAULT_FAKER, random_project
from .helpers.postgres_users import insert_and_get_user_and_secrets_lifespan


@asynccontextmanager
async def _user_context(
    sqlalchemy_async_engine: AsyncEngine, *, name: str
) -> AsyncIterator[UserID]:
    # inject a random user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.
    async with insert_and_get_user_and_secrets_lifespan(
        sqlalchemy_async_engine, name=name
    ) as user:
        yield TypeAdapter(UserID).validate_python(user["id"])


@pytest.fixture
async def user_id(sqlalchemy_async_engine: AsyncEngine) -> AsyncIterator[UserID]:
    async with _user_context(sqlalchemy_async_engine, name="test-user") as new_user_id:
        yield new_user_id


@pytest.fixture
async def other_user_id(sqlalchemy_async_engine: AsyncEngine) -> AsyncIterator[UserID]:
    async with _user_context(
        sqlalchemy_async_engine, name="test-other-user"
    ) as new_user_id:
        yield new_user_id


@pytest.fixture
async def create_project(
    user_id: UserID, sqlalchemy_async_engine: AsyncEngine
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    created_project_uuids = []

    async def _creator(**kwargs) -> dict[str, Any]:
        prj_config = {"prj_owner": user_id}
        prj_config.update(kwargs)
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                projects.insert()
                .values(**random_project(DEFAULT_FAKER, **prj_config))
                .returning(sa.literal_column("*"))
            )
            row = result.one()
            created_project_uuids.append(row.uuid)
            return dict(row._asdict())

    yield _creator
    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_uuids))
        )


@pytest.fixture
async def create_project_access_rights(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[ProjectID, UserID, bool, bool, bool], Awaitable[None]]]:
    _created = []

    async def _creator(
        project_id: ProjectID, user_id: UserID, read: bool, write: bool, delete: bool
    ) -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                project_to_groups.insert()
                .values(
                    project_uuid=f"{project_id}",
                    gid=sa.select(users.c.primary_gid)
                    .where(users.c.id == user_id)
                    .scalar_subquery(),
                    read=read,
                    write=write,
                    delete=delete,
                )
                .returning(sa.literal_column("*"))
            )
            row = result.one()
            _created.append((row.project_uuid, row.gid))

    yield _creator

    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            project_to_groups.delete().where(
                sa.or_(
                    *(
                        (project_to_groups.c.project_uuid == pid)
                        & (project_to_groups.c.gid == gid)
                        for pid, gid in _created
                    )
                )
            )
        )


@pytest.fixture
async def project_id(
    create_project: Callable[[], Awaitable[dict[str, Any]]],
) -> ProjectID:
    project = await create_project()
    return ProjectID(project["uuid"])


@pytest.fixture
async def collaborator_id(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[UserID]:
    async with _user_context(
        sqlalchemy_async_engine, name="collaborator"
    ) as new_user_id:
        yield TypeAdapter(UserID).validate_python(new_user_id)


@pytest.fixture
def share_with_collaborator(
    sqlalchemy_async_engine: AsyncEngine,
    collaborator_id: UserID,
    user_id: UserID,
    project_id: ProjectID,
) -> Callable[[], Awaitable[None]]:
    async def _get_user_group(conn: AsyncConnection, query_user: int) -> int:
        result = await conn.execute(
            sa.select(users.c.primary_gid).where(users.c.id == query_user)
        )
        row = result.fetchone()
        assert row
        primary_gid: int = row.primary_gid
        return primary_gid

    async def _() -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                sa.select(projects.c.access_rights).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            row = result.fetchone()
            assert row
            access_rights: dict[str | int, Any] = row.access_rights

            access_rights[await _get_user_group(conn, user_id)] = {
                "read": True,
                "write": True,
                "delete": True,
            }
            access_rights[await _get_user_group(conn, collaborator_id)] = {
                "read": True,
                "write": True,
                "delete": False,
            }

            await conn.execute(
                projects.update()
                .where(projects.c.uuid == f"{project_id}")
                .values(access_rights=access_rights)
            )

            # project_to_groups needs to be updated
            for group_id, permissions in access_rights.items():
                insert_stmt = pg_insert(project_to_groups).values(
                    project_uuid=f"{project_id}",
                    gid=int(group_id),
                    read=permissions["read"],
                    write=permissions["write"],
                    delete=permissions["delete"],
                    created=sa.func.now(),
                    modified=sa.func.now(),
                )
                on_update_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[
                        project_to_groups.c.project_uuid,
                        project_to_groups.c.gid,
                    ],
                    set_={
                        "read": insert_stmt.excluded.read,
                        "write": insert_stmt.excluded.write,
                        "delete": insert_stmt.excluded.delete,
                        "modified": sa.func.now(),
                    },
                )
                await conn.execute(on_update_stmt)

    return _


@pytest.fixture
async def create_project_node(
    user_id: UserID, sqlalchemy_async_engine: AsyncEngine, faker: Faker
) -> Callable[..., Awaitable[NodeID]]:
    async def _creator(
        project_id: ProjectID, node_id: NodeID | None = None, **kwargs
    ) -> NodeID:
        async with sqlalchemy_async_engine.begin() as conn:
            new_node_id = node_id or NodeID(faker.uuid4())
            node_values = {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "pytest_fake_node",
            }
            node_values.update(**kwargs)
            await conn.execute(
                projects_nodes.insert().values(
                    node_id=f"{new_node_id}",
                    project_uuid=f"{project_id}",
                    **node_values,
                )
            )
        return new_node_id

    return _creator
