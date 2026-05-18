# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    MetadataFilterItem,
)
from models_library.users import UserID
from pydantic import ValidationError
from pytest_simcore.helpers.webserver_projects import NewProject
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
        storage_assets_deleted=False,
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
    assert project.job_parent_resource_name == project_job_fixture.job_parent_resource_name

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
    assert project.job_parent_resource_name == project_job_fixture.job_parent_resource_name

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
    assert project.job_parent_resource_name == project_job_fixture.job_parent_resource_name

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
        storage_assets_deleted=False,
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


async def test_filter_projects_by_metadata_all(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    tests_data_dir: Path,
):
    """Test that list_my_projects_marked_as_jobs can filter projects using AND logic on custom metadata.

    Creates 3 projects with different metadata combinations and verifies that
    filter_all_custom_metadata requires ALL conditions to match (AND logic).
    """
    assert client.app

    user_id = logged_user["id"]

    # Create 3 projects with distinct metadata
    projects_metadata_map: dict[str, MetadataDict] = {
        "solvers/fem-solver/v1": {
            "solver_type": "FEM",
            "mesh_cells": "1000",
            "status": "completed",
        },
        "solvers/fem-solver/v2": {
            "solver_type": "FEM",
            "mesh_cells": "500",
            "status": "pending",
        },
        "solvers/cfd-solver/v1": {
            "solver_type": "CFD",
            "mesh_cells": "1000",
            "status": "completed",
        },
    }

    project_uuids: dict[str, ProjectID] = {}

    async with AsyncExitStack() as stack:
        for job_parent_resource_name, custom_metadata in projects_metadata_map.items():
            project = await stack.enter_async_context(
                NewProject(
                    {"name": f"project-{job_parent_resource_name}"},
                    client.app,
                    user_id=user_id,
                    product_name=osparc_product_name,
                    tests_data_dir=tests_data_dir,
                )
            )
            project_uuid = ProjectID(project["uuid"])
            project_uuids[job_parent_resource_name] = project_uuid

            await set_project_as_job(
                app=client.app,
                product_name=osparc_product_name,
                user_id=user_id,
                project_uuid=project_uuid,
                job_parent_resource_name=job_parent_resource_name,
                storage_assets_deleted=False,
            )

            await set_project_custom_metadata(
                app=client.app,
                user_id=user_id,
                project_uuid=project_uuid,
                value=custom_metadata,
            )

        uuid_a = project_uuids["solvers/fem-solver/v1"]
        uuid_b = project_uuids["solvers/fem-solver/v2"]
        uuid_c = project_uuids["solvers/cfd-solver/v1"]

        # --- AND filter: solver_type=FEM AND mesh_cells=1000 -> only Project A
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_all_custom_metadata=[("solver_type", "FEM"), ("mesh_cells", "1000")],
        )
        assert total_count == 1
        assert result[0].uuid == uuid_a

        # --- AND filter: solver_type=FEM -> Projects A and B
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_all_custom_metadata=[("solver_type", "FEM")],
        )
        assert total_count == 2
        result_uuids = {r.uuid for r in result}
        assert result_uuids == {uuid_a, uuid_b}

        # --- AND filter: status=completed AND mesh_cells=1000 -> Projects A and C
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_all_custom_metadata=[("status", "completed"), ("mesh_cells", "1000")],
        )
        assert total_count == 2
        result_uuids = {r.uuid for r in result}
        assert result_uuids == {uuid_a, uuid_c}

        # --- AND filter: all 3 conditions that no single project matches -> empty
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_all_custom_metadata=[("solver_type", "FEM"), ("status", "pending"), ("mesh_cells", "999")],
        )
        assert total_count == 0
        assert result == []

        # --- AND filter with wildcards: solver_type=FEM AND mesh_cells=1* -> Project A only
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_all_custom_metadata=[("solver_type", "FEM"), ("mesh_cells", "1*")],
        )
        assert total_count == 1
        assert result[0].uuid == uuid_a

        # --- Combining AND filter with job_parent_resource_name_prefix
        total_count, result = await list_my_projects_marked_as_jobs(
            app=client.app,
            product_name=osparc_product_name,
            user_id=user_id,
            filter_by_job_parent_resource_name_prefix="solvers/fem-solver",
            filter_all_custom_metadata=[("status", "completed")],
        )
        assert total_count == 1
        assert result[0].uuid == uuid_a


async def test_filter_all_and_any_custom_metadata_are_mutually_exclusive():
    """Test that setting both any_custom_metadata and all_custom_metadata raises a validation error."""
    with pytest.raises(ValidationError):
        ListProjectsMarkedAsJobRpcFilters(
            any_custom_metadata=[MetadataFilterItem(name="key", pattern="val")],
            all_custom_metadata=[MetadataFilterItem(name="key2", pattern="val2")],
        )
