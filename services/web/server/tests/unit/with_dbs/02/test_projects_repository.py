# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from datetime import datetime, timedelta
from uuid import UUID

import arrow
import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.basic_types import IDStr
from models_library.rest_ordering import OrderBy, OrderDirection
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects import (
    _projects_repository as projects_service_repository,
)
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError
from simcore_service_webserver.projects.models import ProjectDBGet, ProjectDict


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
    got_project = await projects_service_repository.get_project(
        client.app, project_uuid=user_project["uuid"]
    )

    assert got_project.uuid == UUID(user_project["uuid"])
    assert got_project.name == user_project["name"]
    assert got_project.description == user_project["description"]

    # Get non-existent project
    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.get_project(
            client.app, project_uuid=non_existent_project_uuid
        )


async def test_patch_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app

    # This will change after in patched_project
    creation_date = datetime.fromisoformat(user_project["creationDate"])
    last_change_date = datetime.fromisoformat(user_project["lastChangeDate"])
    assert abs(creation_date - last_change_date) < timedelta(seconds=1)

    # Patch valid project
    patch_data = {"name": "Updated Project Name"}
    patched_project = await projects_service_repository.patch_project(
        client.app,
        project_uuid=user_project["uuid"],
        new_partial_project_data=patch_data,
    )

    assert patched_project.uuid == UUID(user_project["uuid"])
    assert patched_project.name == patch_data["name"]
    assert patched_project.creation_date < patched_project.last_change_date

    # Patch non-existent project
    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.patch_project(
            client.app,
            project_uuid=non_existent_project_uuid,
            new_partial_project_data=patch_data,
        )


async def test_delete_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app

    # Delete valid project
    deleted_project = await projects_service_repository.delete_project(
        client.app, project_uuid=user_project["uuid"]
    )

    assert deleted_project.uuid == UUID(user_project["uuid"])

    # Check deleted
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.delete_project(
            client.app, project_uuid=user_project["uuid"]
        )

    # Delete non-existent project
    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProjectNotFoundError):
        await projects_service_repository.delete_project(
            client.app, project_uuid=non_existent_project_uuid
        )


@pytest.fixture
async def trashed_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
) -> ProjectDBGet:
    assert client.app

    # Patch project to be trashed
    trashed_at = arrow.utcnow().datetime
    patch_data = {
        "trashed": trashed_at,
        "trashed_by": logged_user["id"],
        "trashed_explicitly": True,
    }
    return await projects_service_repository.patch_project(
        client.app,
        project_uuid=user_project["uuid"],
        new_partial_project_data=patch_data,
    )


async def test_list_trashed_projects(client: TestClient, trashed_project: ProjectDBGet):
    assert client.app

    (
        total_count,
        trashed_projects,
    ) = await projects_service_repository.list_projects_db_get_as_admin(
        client.app,
        trashed_explicitly=True,
        trashed_before=arrow.utcnow().datetime + timedelta(days=1),
        order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
    )

    assert total_count == 1
    assert len(trashed_projects) == 1
    assert trashed_projects[0] == trashed_project


async def test_get_trashed_by_primary_gid(
    client: TestClient,
    logged_user: UserInfoDict,
    trashed_project: ProjectDBGet,
):
    assert client.app

    # Get trashed by primary gid
    trashed_by_primary_gid = (
        await projects_service_repository.get_trashed_by_primary_gid(
            client.app,
            projects_uuid=trashed_project.uuid,
        )
    )

    assert trashed_by_primary_gid == logged_user["primary_gid"]


async def test_batch_get_trashed_by_primary_gid(
    client: TestClient,
    logged_user: UserInfoDict,
    trashed_project: ProjectDBGet,
):
    assert client.app

    non_existent_project_uuid = UUID("00000000-0000-0000-0000-000000000000")

    # Batch get trashed by primary gid
    trashed_by_primary_gid = (
        await projects_service_repository.batch_get_trashed_by_primary_gid(
            client.app,
            projects_uuids=[
                trashed_project.uuid,
                non_existent_project_uuid,  # non-existent
                trashed_project.uuid,  # repeated
            ],
        )
    )

    assert trashed_by_primary_gid == [
        logged_user["primary_gid"],
        None,
        logged_user["primary_gid"],
    ]
