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
from faker import Faker
from pydantic import TypeAdapter
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects import (
    DBProjectNotFoundError,
    ProjectsRepo,
)
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


async def _delete_project(connection: AsyncConnection, project_uuid: uuid.UUID) -> None:
    await connection.execute(sa.delete(projects).where(projects.c.uuid == f"{project_uuid}"))


@pytest.fixture
async def registered_user(
    asyncpg_connection: AsyncConnection,
    create_fake_user: Callable[..., Awaitable[RowMapping]],
) -> RowMapping:
    user = await create_fake_user(asyncpg_connection)
    assert user
    return user


@pytest.fixture
async def registered_product(
    create_fake_product: Callable[..., Awaitable[RowMapping]],
) -> RowMapping:
    product = await create_fake_product("test-product")
    assert product
    return product


@pytest.fixture
async def registered_project(
    asyncpg_connection: AsyncConnection,
    registered_user: RowMapping,
    registered_product: RowMapping,
    create_fake_project: Callable[..., Awaitable[RowMapping]],
) -> AsyncIterator[dict[str, Any]]:
    project = await create_fake_project(asyncpg_connection, registered_user, registered_product)
    assert project

    yield dict(project)

    await _delete_project(asyncpg_connection, project["uuid"])


@pytest.mark.parametrize("expected", [datetime.now(tz=UTC), None])
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

        row = result.mappings().one()

    assert row
    trashed = TypeAdapter(datetime | None).validate_python(row["trashed"])
    assert trashed == expected


async def test_get_project_last_change_date(asyncpg_engine: AsyncEngine, registered_project: dict, faker: Faker):
    projects_repo = ProjectsRepo(asyncpg_engine)

    project_last_change_date = await projects_repo.get_project_last_change_date(project_uuid=registered_project["uuid"])
    assert isinstance(project_last_change_date, datetime)

    with pytest.raises(DBProjectNotFoundError):
        await projects_repo.get_project_last_change_date(
            project_uuid=faker.uuid4()  # <-- Non existing uuid in DB
        )
