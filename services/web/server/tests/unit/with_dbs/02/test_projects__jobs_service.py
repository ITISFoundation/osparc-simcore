import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.projects._jobs_service import (
    list_my_projects_marked_as_jobs,
    set_project_as_job,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    # for logged_user
    return UserRole.USER


async def test_list_my_projects_marked_as_jobs_empty(
    client: TestClient,
    logged_user: UserInfoDict,  # owns `user_project`
    user_project: ProjectDict,
    osparc_product_name: ProductName,
):
    assert client.app
    assert user_project

    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=logged_user["id"],
    )
    assert total_count == 0
    assert result == []


async def test_list_my_projects_marked_as_jobs_with_one_marked(
    client: TestClient,
    logged_user: UserInfoDict,  # owns `user_project`
    user_project: ProjectDict,
    user: UserInfoDict,
    osparc_product_name: ProductName,
):
    assert client.app

    user_id = logged_user["id"]
    project_uuid = ProjectID(user_project["uuid"])
    other_user_id = user["id"]

    assert user_id != other_user_id
    assert user_project["prjOwner"] == logged_user["email"]  # owns `user_project`

    job_parent_resource_name = "test/resource"
    await set_project_as_job(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )

    # user can see the project
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_uuid
    assert project.job_parent_resource_name == job_parent_resource_name

    # other-user cannot see the project even if it is marked as a job
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=other_user_id,
    )
    assert total_count == 0
    assert len(result) == 0

    # user can see the project with a filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter=job_parent_resource_name,
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_uuid
    assert project.job_parent_resource_name == job_parent_resource_name

    # user can see the project with a wildcard filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter="test/%",
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_uuid
    assert project.job_parent_resource_name == job_parent_resource_name

    # user cannot see the project with another wildcard filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter="other/%",
    )
    assert total_count == 0
    assert len(result) == 0
