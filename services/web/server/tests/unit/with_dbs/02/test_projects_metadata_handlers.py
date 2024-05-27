# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import random
from copy import deepcopy
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.projects_nodes_io import NodeID
from models_library.utils.json_serialization import json_dumps, json_loads
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import NewProject
from pytest_simcore.helpers.utils_webserver_unit_with_db import MockedStorageSubsystem
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects import _crud_api_delete
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4313"
)
@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_custom_metadata_handlers(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    #
    # metadata is a singleton subresource of a project
    # a singleton is implicitly created or deleted when its parent is created or deleted
    #
    assert client.app

    # get metadata of a non-existing project -> Not found
    invalid_project_id = faker.uuid4()
    url = client.app.router["get_project_metadata"].url_for(
        project_id=invalid_project_id
    )
    response = await client.get(f"{url}")

    _, error = await assert_status(
        response, expected_status_code=status.HTTP_404_NOT_FOUND
    )
    error_message = error["errors"][0]["message"]
    assert invalid_project_id in error_message
    assert "project" in error_message.lower()

    # get metadata of an existing project the first time -> empty {}
    url = client.app.router["get_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
    assert data["custom"] == {}

    # replace metadata
    custom_metadata = {"number": 3.14, "string": "str", "boolean": False}
    custom_metadata["other"] = json.dumps(custom_metadata)

    url = client.app.router["update_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.patch(
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
    )

    data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)

    assert parse_obj_as(ProjectMetadataGet, data).custom == custom_metadata

    # delete project
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])
    response = await client.delete(f"{url}")
    await assert_status(response, expected_status_code=status.HTTP_204_NO_CONTENT)

    async def _wait_until_deleted():
        tasks = _crud_api_delete.get_scheduled_tasks(
            project_uuid=user_project["uuid"], user_id=logged_user["id"]
        )
        await tasks[0]

    await _wait_until_deleted()

    # no metadata -> project not found
    url = client.app.router["get_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected_status_code=status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_update_project_metadata_backward_compatibility_with_same_project_raises(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    assert client.app

    child_project = user_project
    # set metadata with fake node_id shall return 404
    custom_metadata = {
        "number": 3.14,
        "string": "str",
        "boolean": False,
        "node_id": faker.uuid4(),
    }
    url = client.app.router["update_project_metadata"].url_for(
        project_id=child_project["uuid"]
    )
    response = await client.patch(
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
    )
    await assert_status(response, expected_status_code=status.HTTP_404_NOT_FOUND)

    # using one of its own nodes as parent is not allowed at the moment
    custom_metadata = {
        "number": 3.14,
        "string": "str",
        "boolean": False,
        "node_id": random.choice(list(child_project["workbench"])),  # noqa: S311,
    }
    url = client.app.router["update_project_metadata"].url_for(
        project_id=child_project["uuid"]
    )
    response = await client.patch(
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
    )
    await assert_status(
        response, expected_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_update_project_metadata_backward_compatibility_with_project_using_same_node_ids_raises(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    assert client.app

    child_project = user_project

    # this is a valid parent project here BUT with the exact same node IDs that raises
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as parent_project_with_same_node_ids:
        random_parent_node_id = NodeID(
            random.choice(  # noqa: S311
                list(parent_project_with_same_node_ids["workbench"])
            )
        )
        custom_metadata = {
            "number": 3.14,
            "string": "str",
            "boolean": False,
            "node_id": f"{random_parent_node_id}",
        }
        url = client.app.router["update_project_metadata"].url_for(
            project_id=child_project["uuid"]
        )
        response = await client.patch(
            f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
        )
        await assert_status(
            response, expected_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_update_project_metadata_backward_compatibility_with_valid_project(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    assert client.app

    child_project = user_project

    # this is a valid parent project with different node IDs
    fake_project_with_different_nodes = deepcopy(fake_project)
    node_mapping = {node_id: faker.uuid4() for node_id in fake_project["workbench"]}
    stringified_workbench = json_dumps(fake_project["workbench"])
    for old_node_id, new_node_id in node_mapping.items():
        stringified_workbench = stringified_workbench.replace(old_node_id, new_node_id)

    fake_project_with_different_nodes["workbench"] = json_loads(stringified_workbench)

    async with NewProject(
        fake_project_with_different_nodes,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as parent_project:
        random_parent_node_id = NodeID(
            random.choice(list(parent_project["workbench"]))  # noqa: S311
        )
        custom_metadata = {
            "number": 3.14,
            "string": "str",
            "boolean": False,
            "node_id": f"{random_parent_node_id}",
        }
        url = client.app.router["update_project_metadata"].url_for(
            project_id=child_project["uuid"]
        )
        response = await client.patch(
            f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
        )
        data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
        assert parse_obj_as(ProjectMetadataGet, data).custom == custom_metadata
        # NOTE: for now the parents are not returned. if this changes, this test should be adapted


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_update_project_metadata_s4lacad_backward_compatibility_passing_nil_parent_node_id(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    assert client.app

    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as child_project:

        # set metadata with node_id set to UUID(0), whih should not raise
        # Notice that the parent project ID is not passed!
        custom_metadata = {
            "number": 3.14,
            "string": "str",
            "boolean": False,
            "node_id": "00000000-0000-0000-0000-000000000000",
        }
        url = client.app.router["update_project_metadata"].url_for(
            project_id=child_project["uuid"]
        )
        response = await client.patch(
            f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).dict()
        )
        data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
        assert parse_obj_as(ProjectMetadataGet, data).custom == custom_metadata
