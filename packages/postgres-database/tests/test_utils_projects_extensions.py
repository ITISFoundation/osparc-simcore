# pylint: disable=redefined-outer-name

from collections.abc import Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from simcore_postgres_database.utils_projects_extensions import ProjectsExtensionsRepo
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def fake_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    user: RowProxy = await create_fake_user(connection, name=f"user.{__name__}")
    return user


@pytest.fixture
async def fake_project(
    connection: SAConnection,
    fake_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_nodes: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    project: RowProxy = await create_fake_project(connection, fake_user, hidden=True)
    await create_fake_nodes(project)
    return project


async def test_workflow(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)

    assert (
        await ProjectsExtensionsRepo.allows_guests_to_push_states_and_output_ports(
            asyncpg_engine, project_uuid=project["uuid"]
        )
        is False
    )

    # add the entry in the table
    await ProjectsExtensionsRepo.set_allow_guests_to_push_states_and_output_ports(
        asyncpg_engine, project_uuid=project["uuid"]
    )

    assert (
        await ProjectsExtensionsRepo.allows_guests_to_push_states_and_output_ports(
            asyncpg_engine, project_uuid=project["uuid"]
        )
        is True
    )
