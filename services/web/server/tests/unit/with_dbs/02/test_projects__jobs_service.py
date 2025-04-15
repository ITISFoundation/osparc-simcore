from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.projects._jobs_service import (
    list_my_projects_marked_as_jobs,
    set_project_as_job,
)
from simcore_service_webserver.projects.models import ProjectDict


async def test_list_my_projects_marked_as_jobs_empty(
    client: TestClient,
    logged_user: UserInfoDict,  # owns `user_project`
    osparc_product_name: ProductName,
    user_project: ProjectDict,
):
    assert client.app
    assert user_project

    result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=logged_user["id"],
    )
    assert result == []


async def test_list_my_projects_marked_as_jobs_with_one_marked(
    client: TestClient,
    logged_user: UserInfoDict,  # owns `user_project`
    osparc_product_name: ProductName,
    user_project: ProjectDict,
):
    assert client.app

    user_id = logged_user["id"]
    project_uuid = user_project["uuid"]
    job_parent_resource_name = "test/resource"

    await set_project_as_job(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )

    result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
    )
    assert len(result) == 1
    assert result[0]["project_uuid"] == project_uuid
    assert result[0]["job_parent_resource_name"] == job_parent_resource_name

    result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter=job_parent_resource_name,
    )
    assert len(result) == 1

    result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter="test/%",
    )
    assert len(result) == 1

    result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        job_parent_resource_name_filter="other/%",
    )
    assert len(result) == 0
