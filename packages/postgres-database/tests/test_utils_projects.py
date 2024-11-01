# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, AsyncIterator

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


@pytest.mark.parametrize("expected", (datetime.now(tz=timezone.utc), None))
async def test_get_project_trashed_at_column_can_be_converted_to_datetime(
    asyncpg_engine: AsyncEngine, registered_project: dict, expected: datetime | None
):
    project_id = registered_project["uuid"]

    async with transaction_context(asyncpg_engine) as conn:
        result = await conn.execute(
            projects.update()
            .values(trashed_at=expected)
            .where(projects.c.uuid == project_id)
            .returning(sa.literal_column("*"))
        )

        row = result.fetchone()

    trashed_at = TypeAdapter(datetime | None).validate_python(row.trashed_at)
    assert trashed_at == expected


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
