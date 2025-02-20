# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.projects import (
    _projects_db as projects_service_repository,
)
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_get_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app

    # Get valid project
    got = await projects_service_repository.get_project(
        client.app, project_uuid=user_project["uuid"]
    )

    assert got.uuid == UUID(user_project["uuid"])
    assert got.name == user_project["name"]
    assert got.description == user_project["description"]

    # Get non-existent project
    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.get_project(
            client.app, project_uuid=non_existent_project_uuid
        )
