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
    DBProjectInvalidAncestorsError,
    DBProjectInvalidParentNodeError,
    DBProjectInvalidParentProjectError,
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
async def test_set_project_custom_metadata(
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
        await utils_projects_metadata.set_project_custom_metadata(
            connection,
            project_uuid=random_project_uuid,
            custom_metadata=user_metadata,
        )

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None
    assert project_metadata.root_parent_project_uuid is None
    assert project_metadata.root_parent_node_id is None

    got = await utils_projects_metadata.set_project_custom_metadata(
        connection,
        project_uuid=project["uuid"],
        custom_metadata=user_metadata,
    )
    assert got.custom
    assert got.parent_project_uuid is None
    assert got.parent_node_id is None
    assert got.root_parent_project_uuid is None
    assert got.root_parent_node_id is None
    assert user_metadata == got.custom

    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata == got

    got_after_update = await utils_projects_metadata.set_project_custom_metadata(
        connection,
        project_uuid=project["uuid"],
        custom_metadata={},
    )
    assert got_after_update.custom == {}
    assert got.modified
    assert got_after_update.modified
    assert got.modified < got_after_update.modified


async def test_set_project_ancestors_with_invalid_parents(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
    faker: Faker,
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)
    project_node = await create_fake_projects_node(project["uuid"])

    # this is empty
    project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None
    assert project_metadata.root_parent_project_uuid is None
    assert project_metadata.root_parent_node_id is None

    random_project_uuid = faker.uuid4(cast_to=None)
    assert isinstance(random_project_uuid, UUID)
    random_node_id = faker.uuid4(cast_to=None)
    assert isinstance(random_node_id, UUID)

    # invalid project
    with pytest.raises(DBProjectNotFoundError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=random_project_uuid,
            parent_project_uuid=None,
            parent_node_id=None,
        )

    # test invalid combinations
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=None,
        )
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project["uuid"],
            parent_project_uuid=None,
            parent_node_id=random_node_id,
        )

    # valid combination with invalid project/node
    with pytest.raises(DBProjectInvalidParentProjectError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=random_node_id,
        )

    # these would make it a parent of itself which is forbiden
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=random_node_id,
        )

    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=project_node.node_id,
        )

    #
    another_project = await create_fake_project(connection, user, hidden=False)
    with pytest.raises(DBProjectInvalidParentNodeError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=another_project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=random_node_id,
        )

    with pytest.raises(DBProjectInvalidParentProjectError):
        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=another_project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=project_node.node_id,
        )


async def test_set_project_ancestors(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
    faker: Faker,
):
    user: RowProxy = await create_fake_user(connection)

    # create grand-parent
    grand_parent_project = await create_fake_project(connection, user, hidden=False)
    grand_parent_node = await create_fake_projects_node(grand_parent_project["uuid"])

    # create parent
    parent_project = await create_fake_project(connection, user, hidden=False)
    parent_node = await create_fake_projects_node(parent_project["uuid"])

    # create child
    child_project: RowProxy = await create_fake_project(connection, user, hidden=True)

    # set ancestry, first the parents
    updated_parent_metadata = await utils_projects_metadata.set_project_ancestors(
        connection,
        project_uuid=parent_project["uuid"],
        parent_project_uuid=grand_parent_project["uuid"],
        parent_node_id=grand_parent_node.node_id,
    )
    assert updated_parent_metadata.parent_project_uuid == uuid.UUID(
        grand_parent_project["uuid"]
    )
    assert updated_parent_metadata.parent_node_id == grand_parent_node.node_id
    assert updated_parent_metadata.root_parent_project_uuid == uuid.UUID(
        grand_parent_project["uuid"]
    )
    assert updated_parent_metadata.root_parent_node_id == grand_parent_node.node_id

    # then the child
    updated_child_metadata = await utils_projects_metadata.set_project_ancestors(
        connection,
        project_uuid=child_project["uuid"],
        parent_project_uuid=parent_project["uuid"],
        parent_node_id=parent_node.node_id,
    )
    assert updated_child_metadata.parent_project_uuid == uuid.UUID(
        parent_project["uuid"]
    )
    assert updated_child_metadata.parent_node_id == parent_node.node_id
    assert updated_child_metadata.root_parent_project_uuid == uuid.UUID(
        grand_parent_project["uuid"]
    )
    assert updated_child_metadata.root_parent_node_id == grand_parent_node.node_id

    # check properly updated
    returned_project_metadata = await utils_projects_metadata.get(
        connection, project_uuid=child_project["uuid"]
    )
    assert returned_project_metadata == updated_child_metadata

    # remove the child
    updated_child_metadata = await utils_projects_metadata.set_project_ancestors(
        connection,
        project_uuid=child_project["uuid"],
        parent_project_uuid=None,
        parent_node_id=None,
    )
    assert updated_child_metadata.parent_project_uuid is None
    assert updated_child_metadata.parent_node_id is None
    assert updated_child_metadata.root_parent_project_uuid is None
    assert updated_child_metadata.root_parent_node_id is None
