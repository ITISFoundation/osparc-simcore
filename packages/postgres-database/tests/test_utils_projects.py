# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pydantic import TypeAdapter
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects import (
    DBProjectNotFoundError,
    ProjectsRepo,
)
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine


async def _delete_project(connection: SAConnection, project_uuid: uuid.UUID) -> None:
    result = await connection.execute(
        sa.delete(projects).where(projects.c.uuid == f"{project_uuid}")
    )
    assert result.rowcount == 1


@pytest.fixture
async def registered_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    user = await create_fake_user(connection)
    assert user
    return user


@pytest.fixture
async def registered_project(
    connection: SAConnection,
    registered_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> AsyncIterator[dict[str, Any]]:
    project = await create_fake_project(connection, registered_user)
    assert project

    yield dict(project)

    await _delete_project(connection, project["uuid"])


@pytest.mark.parametrize("expected", (datetime.now(tz=UTC), None))
async def test_get_project_trashed_column_can_be_converted_to_datetime(
    asyncpg_engine: AsyncEngine, registered_project: dict, expected: datetime | None
):
    project_id = registered_project["uuid"]

    async with transaction_context(asyncpg_engine) as conn:
        result = await conn.execute(
            projects.update()
            .values(trashed=expected)
            .where(projects.c.uuid == project_id)
            .returning(sa.literal_column("*"))
        )

        row = result.fetchone()

    assert row
    trashed = TypeAdapter(datetime | None).validate_python(row.trashed)
    assert trashed == expected


@pytest.mark.parametrize("with_explicit_connection", [True, False])
async def test_projects_repo_exists_with_existing_project(
    asyncpg_engine: AsyncEngine,
    registered_project: dict,
    with_explicit_connection: bool,
):
    projects_repo = ProjectsRepo(asyncpg_engine)
    project_uuid = registered_project["uuid"]

    if with_explicit_connection:
        async with transaction_context(asyncpg_engine) as conn:
            exists = await projects_repo.exists(project_uuid, connection=conn)
    else:
        exists = await projects_repo.exists(project_uuid)

    assert exists is True


@pytest.mark.parametrize("with_explicit_connection", [True, False])
async def test_projects_repo_exists_with_non_existing_project(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    with_explicit_connection: bool,
):
    projects_repo = ProjectsRepo(asyncpg_engine)
    non_existing_uuid = faker.uuid4()

    if with_explicit_connection:
        async with transaction_context(asyncpg_engine) as conn:
            exists = await projects_repo.exists(non_existing_uuid, connection=conn)
    else:
        exists = await projects_repo.exists(non_existing_uuid)

    assert exists is False


async def test_get_project_last_change_date(
    asyncpg_engine: AsyncEngine, registered_project: dict, faker: Faker
):
    projects_repo = ProjectsRepo(asyncpg_engine)

    project_last_change_date = await projects_repo.get_project_last_change_date(
        project_uuid=registered_project["uuid"]
    )
    assert isinstance(project_last_change_date, datetime)

    with pytest.raises(DBProjectNotFoundError):
        await projects_repo.get_project_last_change_date(
            project_uuid=faker.uuid4()  # <-- Non existing uuid in DB
        )
