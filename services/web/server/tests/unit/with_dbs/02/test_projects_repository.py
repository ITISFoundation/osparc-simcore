# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.projects import (
    _projects_db as projects_service_repository,
)
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError
from simcore_service_webserver.projects.models import ProjectDict


async def test_get_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    assert client.app

    # Insert a project into the database
    new_project = await insert_project_in_db(user_project, user_id=logged_user["id"])

    # Retrieve the project using the repository function
    retrieved_project = await projects_service_repository.get_project(
        client.app, project_uuid=UUID(new_project["uuid"])
    )

    # Validate the retrieved project
    assert retrieved_project.uuid == new_project["uuid"]
    assert retrieved_project.name == new_project["name"]
    assert retrieved_project.description == new_project["description"]

    # Test retrieving a non-existent project
    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.get_project(
            client.app, project_uuid=non_existent_project_uuid
        )
