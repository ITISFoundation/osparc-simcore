# pylint: disable=protected-access
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
    project: RowProxy = await create_fake_project(connection, fake_user)
    await create_fake_nodes(project)
    return project


async def _assert_allows_to_psuh(
    asyncpg_engine: AsyncEngine, project_uuid: str, *, expected: bool
) -> None:
    result = await ProjectsExtensionsRepo.allows_guests_to_push_states_and_output_ports(
        asyncpg_engine, project_uuid=project_uuid
    )
    assert result is expected


async def test_workflow(
    asyncpg_engine: AsyncEngine,
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user)

    await _assert_allows_to_psuh(asyncpg_engine, project["uuid"], expected=False)

    # add the entry in the table
    await ProjectsExtensionsRepo._set_allow_guests_to_push_states_and_output_ports(
        asyncpg_engine, project_uuid=project["uuid"]
    )

    await _assert_allows_to_psuh(asyncpg_engine, project["uuid"], expected=True)

    copy_project: RowProxy = await create_fake_project(connection, user)

    assert (
        await ProjectsExtensionsRepo.allows_guests_to_push_states_and_output_ports(
            asyncpg_engine, project_uuid=copy_project["uuid"]
        )
        is False
    )
    await _assert_allows_to_psuh(asyncpg_engine, copy_project["uuid"], expected=False)
    await ProjectsExtensionsRepo.copy_allow_guests_to_push_states_and_output_ports(
        asyncpg_engine,
        from_project_uuid=project["uuid"],
        to_project_uuid=copy_project["uuid"],
    )
    await _assert_allows_to_psuh(asyncpg_engine, copy_project["uuid"], expected=True)
