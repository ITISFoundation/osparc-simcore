# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.projects_nodes import Node, PartialNode
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects import _projects_nodes_repository
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_add_to_non_existent_project_raises_project_not_found(client: TestClient, logged_user: UserInfoDict):
    assert client.app
    with pytest.raises(ProjectNotFoundError):
        await _projects_nodes_repository.add(
            client.app,
            project_id=uuid4(),
            node_id=uuid4(),
            node=Node.model_construct(key="simcore/services/comp/is4cpu", version="1.0.0", label="x"),
        )


async def test_update_of_non_existent_project_raises_project_not_found(client: TestClient, logged_user: UserInfoDict):
    assert client.app
    with pytest.raises(ProjectNotFoundError):
        await _projects_nodes_repository.update(
            client.app,
            project_id=uuid4(),
            node_id=uuid4(),
            partial_node=PartialNode.model_construct(progress=42.0),
        )


async def test_delete_of_non_existent_project_raises_project_not_found(client: TestClient, logged_user: UserInfoDict):
    assert client.app
    with pytest.raises(ProjectNotFoundError):
        await _projects_nodes_repository.delete(client.app, project_id=uuid4(), node_id=uuid4())
