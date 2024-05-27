# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import uuid
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database import utils_projects_metadata
from simcore_postgres_database.utils_projects_metadata import (
    DBProjectNodeParentNotFoundError,
    DBProjectNotFoundError,
)
from simcore_postgres_database.utils_projects_nodes import ProjectNode


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
    random_project_uuid = faker.uuid4(cast_to=None)
    assert isinstance(random_project_uuid, UUID)
    with pytest.raises(DBProjectNotFoundError):
        await utils_projects_metadata.get(connection, project_uuid=random_project_uuid)

    with pytest.raises(DBProjectNotFoundError):
        await utils_projects_metadata.upsert(
            connection,
            project_uuid=random_project_uuid,
            custom_metadata=user_metadata,
            parent_project_uuid=None,
            parent_node_id=None,
        )

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None

    got = await utils_projects_metadata.upsert(
        connection,
        project_uuid=project["uuid"],
        custom_metadata=user_metadata,
        parent_project_uuid=None,
        parent_node_id=None,
    )
    assert got.custom
    assert got.parent_project_uuid is None
    assert got.parent_node_id is None
    assert user_metadata == got.custom

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata == got

    got_after_update = await utils_projects_metadata.upsert(
        connection,
        project_uuid=project["uuid"],
        custom_metadata={},
        parent_project_uuid=None,
        parent_node_id=None,
    )
    assert got_after_update.custom == {}
    assert got.modified
    assert got_after_update.modified
    assert got.modified < got_after_update.modified


async def test_projects_metadata_repository_invalid_parents(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    faker: Faker,
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)

    # this is empty
    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None

    random_project_uuid = faker.uuid4(cast_to=None)
    assert isinstance(random_project_uuid, UUID)

    with pytest.raises(DBProjectNodeParentNotFoundError):
        # invalid combination
        await utils_projects_metadata.upsert(
            connection,
            project_uuid=project["uuid"],
            custom_metadata=faker.pydict(allowed_types=(str,)),
            parent_project_uuid=random_project_uuid,
            parent_node_id=None,
        )

    random_node_id = faker.uuid4(cast_to=None)
    assert isinstance(random_node_id, UUID)
    with pytest.raises(DBProjectNodeParentNotFoundError):
        # not existing
        await utils_projects_metadata.upsert(
            connection,
            project_uuid=project["uuid"],
            custom_metadata=faker.pydict(allowed_types=(str,)),
            parent_project_uuid=random_project_uuid,
            parent_node_id=random_node_id,
        )

    with pytest.raises(DBProjectNodeParentNotFoundError):
        # invalid combination
        await utils_projects_metadata.upsert(
            connection,
            project_uuid=project["uuid"],
            custom_metadata=faker.pydict(allowed_types=(str,)),
            parent_project_uuid=None,
            parent_node_id=random_node_id,
        )


async def test_projects_metadata_repository_with_parent_project(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
    faker: Faker,
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)

    # this is empty
    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None

    # create parent project and node
    parent_project = await create_fake_project(connection, user, hidden=False)
    parent_node = await create_fake_projects_node(parent_project["uuid"])
    updated_project_metadata = await utils_projects_metadata.upsert(
        connection,
        project_uuid=project["uuid"],
        custom_metadata=faker.pydict(allowed_types=(str,)),
        parent_project_uuid=parent_project["uuid"],
        parent_node_id=parent_node.node_id,
    )
    assert updated_project_metadata.parent_project_uuid == uuid.UUID(
        parent_project["uuid"]
    )
    assert updated_project_metadata.parent_node_id == parent_node.node_id

    # check properly updated
    returned_project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert returned_project_metadata == updated_project_metadata
