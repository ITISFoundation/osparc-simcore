# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from dataclasses import dataclass

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects._jobs_service import (
    list_my_projects_marked_as_jobs,
    set_project_as_job,
)
from simcore_service_webserver.projects._metadata_service import (
    set_project_custom_metadata,
)
from simcore_service_webserver.projects.models import ProjectDict


@dataclass
class ProjectJobFixture:
    user_id: UserID
    project_uuid: ProjectID
    job_parent_resource_name: str
    custom_metadata: MetadataDict | None = None


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
        filter_by_job_parent_resource_name_prefix=project_job_fixture.job_parent_resource_name,
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
        filter_by_job_parent_resource_name_prefix="test/%",
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
        filter_by_job_parent_resource_name_prefix="other/%",
    )
    assert total_count == 0
    assert len(result) == 0


async def test_filter_projects_by_metadata(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
):
    """Test that list_my_projects_marked_as_jobs can filter projects by custom metadata"""
    assert client.app

    user_id = logged_user["id"]
    project_uuid = ProjectID(user_project["uuid"])
    job_parent_resource_name = "test/resource/metadata"

    # 1. Mark the project as a job
    await set_project_as_job(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )

    # 2. Set custom metadata
    custom_metadata: MetadataDict = {
        "test_key": "test_value",
        "category": "simulation",
        "status": "completed",
    }
    await set_project_custom_metadata(
        app=client.app,
        user_id=user_id,
        project_uuid=project_uuid,
        value=custom_metadata,
    )

    # 3. Filter by exact metadata
    filter_exact = [("test_key", "test_value")]
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_any_custom_metadata=filter_exact,
    )
    assert total_count == 1
    assert len(result) == 1
    assert result[0].uuid == project_uuid

    # 4. Filter by multiple metadata keys in one dict (AND condition)
    filter_multiple_keys = [
        ("category", "simulation"),
        ("status", "completed"),
    ]
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_any_custom_metadata=filter_multiple_keys,
    )
    assert total_count == 1
    assert len(result) == 1
    assert result[0].uuid == project_uuid

    # 5. Filter by alternative metadata (OR condition)
    filter_alternative = [
        ("status", "completed"),
        ("status", "pending"),
    ]
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_any_custom_metadata=filter_alternative,
    )
    assert total_count == 1
    assert len(result) == 1
    assert result[0].uuid == project_uuid

    # 6. Filter by non-matching metadata
    filter_non_matching = [("status", "failed")]
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_any_custom_metadata=filter_non_matching,
    )
    assert total_count == 0
    assert len(result) == 0

    # 7. Filter by wildcard pattern (requires SQL LIKE syntax)
    # This assumes the implementation supports wildcards in metadata values
    filter_wildcard = [("test_key", "test_*")]
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_any_custom_metadata=filter_wildcard,
    )
    assert total_count == 1
    assert len(result) == 1
    assert result[0].uuid == project_uuid

    # 8. Combine with parent resource name filter
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_by_job_parent_resource_name_prefix="test/resource",
        filter_any_custom_metadata=[("category", "simulation")],
    )
    assert total_count == 1
    assert len(result) == 1
    assert result[0].uuid == project_uuid

    # 9. Conflicting filters should return no results
    total_count, result = await list_my_projects_marked_as_jobs(
        app=client.app,
        product_name=osparc_product_name,
        user_id=user_id,
        filter_by_job_parent_resource_name_prefix="non-matching",
        filter_any_custom_metadata=[("category", "simulation")],
    )
    assert total_count == 0
    assert len(result) == 0
