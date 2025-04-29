# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from dataclasses import dataclass

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.projects._job_service import (
    list_my_projects_marked_as_jobs,
    set_project_as_job,
)
from simcore_service_webserver.projects.models import ProjectDict


@dataclass
class ProjectJobFixture:
    user_id: UserID
    project_uuid: ProjectID
    job_parent_resource_name: str


@pytest.fixture
def user_role() -> UserRole:
    # for logged_user
    return UserRole.USER


@pytest.fixture
async def project_job_fixture(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
) -> ProjectJobFixture:
    assert client.app

    user_id = logged_user["id"]
    project_uuid = ProjectID(user_project["uuid"])
    job_parent_resource_name = "test/resource"

    await set_project_as_job(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    return ProjectJobFixture(
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )


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


async def test_user_can_see_marked_project(
    client: TestClient,
    osparc_product_name: ProductName,
    project_job_fixture: ProjectJobFixture,
    user_project: ProjectDict,
):
    assert client.app
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=project_job_fixture.user_id,
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_job_fixture.project_uuid
    assert (
        project.job_parent_resource_name == project_job_fixture.job_parent_resource_name
    )

    # Verify workbench structure is maintained
    assert project.workbench is not None
    assert isinstance(project.workbench, dict)

    # Compare with original user_project
    assert len(project.workbench) == len(user_project["workbench"])

    # Check that all node IDs from original project are present
    for node_id in user_project["workbench"]:
        assert node_id in project.workbench

        # Check some properties of the nodes
        original_node = user_project["workbench"][node_id]
        project_node = project.workbench[node_id]

        assert project_node.key == original_node["key"]
        assert project_node.version == original_node["version"]
        assert project_node.label == original_node["label"]

        # Check inputs/outputs if they exist
        if "inputs" in original_node:
            assert project_node.inputs is not None
            assert len(project_node.inputs) == len(original_node["inputs"])

        if "outputs" in original_node:
            assert project_node.outputs is not None
            assert len(project_node.outputs) == len(original_node["outputs"])


async def test_other_user_cannot_see_marked_project(
    client: TestClient,
    user: UserInfoDict,
    osparc_product_name: ProductName,
    project_job_fixture: ProjectJobFixture,
):
    assert client.app
    other_user_id = user["id"]
    assert project_job_fixture.user_id != other_user_id

    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=other_user_id,
    )
    assert total_count == 0
    assert len(result) == 0


async def test_user_can_filter_marked_project(
    client: TestClient,
    osparc_product_name: ProductName,
    project_job_fixture: ProjectJobFixture,
):
    assert client.app

    # Exact filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=project_job_fixture.user_id,
        job_parent_resource_name_prefix=project_job_fixture.job_parent_resource_name,
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_job_fixture.project_uuid
    assert (
        project.job_parent_resource_name == project_job_fixture.job_parent_resource_name
    )

    # Wildcard filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=project_job_fixture.user_id,
        job_parent_resource_name_prefix="test/%",
    )
    assert total_count == 1
    assert len(result) == 1

    project = result[0]
    assert project.uuid == project_job_fixture.project_uuid
    assert (
        project.job_parent_resource_name == project_job_fixture.job_parent_resource_name
    )

    # Non-matching filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=project_job_fixture.user_id,
        job_parent_resource_name_prefix="other/%",
    )
    assert total_count == 0
    assert len(result) == 0
