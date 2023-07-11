# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database import utils_projects_metadata
from simcore_postgres_database.utils_projects_metadata import DBProjectNotFoundError


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


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4313"
)
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
        await utils_projects_metadata.get(connection, project_uuid=faker.uuid4())

    with pytest.raises(DBProjectNotFoundError):
        await utils_projects_metadata.upsert(
            connection, project_uuid=faker.uuid4(), custom_metadata=user_metadata
        )

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None

    got = await utils_projects_metadata.upsert(
        connection, project_uuid=project["uuid"], custom_metadata=user_metadata
    )
    assert got.custom
    assert user_metadata == got.custom

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata == got

    got_after_update = await utils_projects_metadata.upsert(
        connection, project_uuid=project["uuid"], custom_metadata={}
    )
    assert got_after_update.custom == {}
    assert got.modified
    assert got_after_update.modified
    assert got.modified < got_after_update.modified
