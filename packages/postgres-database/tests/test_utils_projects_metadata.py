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
from sqlalchemy.ext.asyncio import AsyncConnection


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
    connection_factory: SAConnection | AsyncConnection,
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
        await utils_projects_metadata.get(
            connection_factory, project_uuid=random_project_uuid
        )

    with pytest.raises(DBProjectNotFoundError):
        await utils_projects_metadata.set_project_custom_metadata(
            connection_factory,
            project_uuid=random_project_uuid,
            custom_metadata=user_metadata,
        )

    project_metadata = await utils_projects_metadata.get(
        connection_factory, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata.custom is None
    assert project_metadata.parent_project_uuid is None
    assert project_metadata.parent_node_id is None
    assert project_metadata.root_parent_project_uuid is None
    assert project_metadata.root_parent_node_id is None

    got = await utils_projects_metadata.set_project_custom_metadata(
        connection_factory,
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
        connection_factory, project_uuid=project["uuid"]
    )
    assert project_metadata is not None
    assert project_metadata == got

    got_after_update = await utils_projects_metadata.set_project_custom_metadata(
        connection_factory,
        project_uuid=project["uuid"],
        custom_metadata={},
    )
    assert got_after_update.custom == {}
    assert got.modified
    assert got_after_update.modified
    assert got.modified < got_after_update.modified


async def test_set_project_ancestors_with_invalid_parents(
    connection: SAConnection,
    connection_factory: SAConnection | AsyncConnection,
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
        connection_factory, project_uuid=project["uuid"]
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
            connection_factory,
            project_uuid=random_project_uuid,
            parent_project_uuid=None,
            parent_node_id=None,
        )

    # test invalid combinations
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=None,
        )
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=None,
            parent_node_id=random_node_id,
        )

    # valid combination with invalid project/node
    with pytest.raises(DBProjectInvalidParentProjectError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=random_node_id,
        )

    # these would make it a parent of itself which is forbiden
    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=random_node_id,
        )

    with pytest.raises(DBProjectInvalidAncestorsError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=project_node.node_id,
        )

    #
    another_project = await create_fake_project(connection, user, hidden=False)
    another_project_node = await create_fake_projects_node(another_project["uuid"])
    with pytest.raises(DBProjectInvalidParentNodeError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=another_project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=random_node_id,
        )

    with pytest.raises(DBProjectInvalidParentProjectError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=another_project["uuid"],
            parent_project_uuid=random_project_uuid,
            parent_node_id=project_node.node_id,
        )

    # mix a node from one project and a parent project
    yet_another_project = await create_fake_project(connection, user, hidden=False)
    with pytest.raises(DBProjectInvalidParentNodeError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=yet_another_project["uuid"],
            parent_project_uuid=project["uuid"],
            parent_node_id=another_project_node.node_id,
        )

    with pytest.raises(DBProjectInvalidParentNodeError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=yet_another_project["uuid"],
            parent_project_uuid=another_project["uuid"],
            parent_node_id=project_node.node_id,
        )


async def test_set_project_ancestors(
    connection: SAConnection,
    connection_factory: SAConnection | AsyncConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
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
        connection_factory,
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
        connection_factory,
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
        connection_factory, project_uuid=child_project["uuid"]
    )
    assert returned_project_metadata == updated_child_metadata

    # remove the child
    updated_child_metadata = await utils_projects_metadata.set_project_ancestors(
        connection_factory,
        project_uuid=child_project["uuid"],
        parent_project_uuid=None,
        parent_node_id=None,
    )
    assert updated_child_metadata.parent_project_uuid is None
    assert updated_child_metadata.parent_node_id is None
    assert updated_child_metadata.root_parent_project_uuid is None
    assert updated_child_metadata.root_parent_node_id is None


async def _create_child_project(
    connection: SAConnection,
    connection_factory: SAConnection | AsyncConnection,
    user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
    parent_project: RowProxy | None,
    parent_node: ProjectNode | None,
) -> tuple[RowProxy, ProjectNode]:
    project = await create_fake_project(connection, user, hidden=False)
    node = await create_fake_projects_node(project["uuid"])
    if parent_project and parent_node:
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=project["uuid"],
            parent_project_uuid=parent_project["uuid"],
            parent_node_id=parent_node.node_id,
        )
    return project, node


@pytest.fixture
async def create_projects_genealogy(
    connection: SAConnection,
    connection_factory: SAConnection | AsyncConnection,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
) -> Callable[[RowProxy], Awaitable[list[tuple[RowProxy, ProjectNode]]]]:
    async def _(user: RowProxy) -> list[tuple[RowProxy, ProjectNode]]:
        ancestors: list[tuple[RowProxy, ProjectNode]] = []

        ancestor_project = await create_fake_project(connection, user, hidden=False)
        ancestor_node = await create_fake_projects_node(ancestor_project["uuid"])
        ancestors.append((ancestor_project, ancestor_node))

        for _ in range(13):
            child_project, child_node = await _create_child_project(
                connection,
                connection_factory,
                user,
                create_fake_project,
                create_fake_projects_node,
                ancestor_project,
                ancestor_node,
            )
            ancestor_project = child_project
            ancestor_node = child_node
            ancestors.append((child_project, child_node))

        return ancestors

    return _


async def test_not_implemented_use_cases(
    connection: SAConnection,
    connection_factory: SAConnection | AsyncConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
    create_projects_genealogy: Callable[
        [RowProxy], Awaitable[list[tuple[RowProxy, ProjectNode]]]
    ],
):
    """This will tests use-cases that are currently not implemented and that are expected to fail with an exception
    Basically any project with children cannot have a change in its genealogy anymore. yes children are sacred.
    If you still want to change them you need to go first via the children.
    """
    user = await create_fake_user(connection)
    # add a missing parent to an already existing chain of parent-children
    ancestors = await create_projects_genealogy(user)
    missing_parent_project = await create_fake_project(connection, user)
    missing_parent_node = await create_fake_projects_node(
        missing_parent_project["uuid"]
    )

    with pytest.raises(NotImplementedError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=ancestors[0][0]["uuid"],
            parent_project_uuid=missing_parent_project["uuid"],
            parent_node_id=missing_parent_node.node_id,
        )

    # modifying a parent-child relationship in the middle of the genealogy is also not implemented
    with pytest.raises(NotImplementedError):
        await utils_projects_metadata.set_project_ancestors(
            connection_factory,
            project_uuid=ancestors[3][0]["uuid"],
            parent_project_uuid=missing_parent_project["uuid"],
            parent_node_id=missing_parent_node.node_id,
        )


async def test_model_dump_as_node(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[[uuid.UUID], Awaitable[ProjectNode]],
):
    user: RowProxy = await create_fake_user(connection)
    project: RowProxy = await create_fake_project(connection, user, hidden=True)
    project_node = await create_fake_projects_node(project["uuid"])

    node_data = project_node.model_dump_as_node()
    assert isinstance(node_data, dict)
    assert node_data["key"] == project_node.key
    assert "node_id" not in node_data, "this is only in ProjectNode but not in Node!"
