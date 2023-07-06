# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.utils_projects_metadata import (
    DBProjectNotFoundError,
    ProjectMetadataRepo,
)


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
) -> RowProxy:
    project: RowProxy = await create_fake_project(connection, fake_user, hidden=True)
    return project


async def test_projects_metadata_repository(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    faker: Faker,
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)

    # subresource is attached to parent
    user_metadata = {"float": 3.14, "int": 42, "string": "foo", "bool": True}

    with pytest.raises(DBProjectNotFoundError):
        await ProjectMetadataRepo.get(connection, project_uuid=faker.uuid4())

    with pytest.raises(DBProjectNotFoundError):
        await ProjectMetadataRepo.upsert(
            connection, project_uuid=faker.uuid4(), custom_metadata=user_metadata
        )

    pm = await ProjectMetadataRepo.get(connection, project_uuid=project["uuid"])
    assert pm is not None
    assert pm.custom_metadata is None

    got = await ProjectMetadataRepo.upsert(
        connection, project_uuid=project["uuid"], custom_metadata=user_metadata
    )
    assert got.custom_metadata
    assert user_metadata == got.custom_metadata

    pm = await ProjectMetadataRepo.get(connection, project_uuid=project["uuid"])
    assert pm is not None
    assert pm == got

    got2 = await ProjectMetadataRepo.upsert(
        connection, project_uuid=project["uuid"], custom_metadata={}
    )
    assert got2.custom_metadata == {}
    assert got.modified
    assert got2.modified
    assert got.modified < got2.modified

    # list jobs of a study
    # list all jobs of a user
    # list projects that are non-jobs

    # DELETE job by deleting project
