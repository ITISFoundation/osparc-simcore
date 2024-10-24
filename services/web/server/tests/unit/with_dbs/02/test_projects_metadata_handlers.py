# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import random
from collections.abc import Awaitable, Callable

import aiopg
import aiopg.sa
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_user_role_response,
)
from servicelib.aiohttp import status
from simcore_postgres_database.utils_projects_metadata import (
    get as get_db_project_metadata,
)
from simcore_service_webserver.projects import _crud_api_delete
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4313"
)
@pytest.mark.parametrize(*standard_user_role_response())
async def test_custom_metadata_handlers(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
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

    _, error = await assert_status(response, expected_status_code=expected.not_found)
    error_message = error["errors"][0]["message"]
    assert invalid_project_id in error_message
    assert "project" in error_message.lower()

    # get metadata of an existing project the first time -> empty {}
    url = client.app.router["get_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, expected_status_code=expected.ok)
    assert data["custom"] == {}

    # replace metadata
    custom_metadata = {"number": 3.14, "string": "str", "boolean": False}
    custom_metadata["other"] = json.dumps(custom_metadata)

    url = client.app.router["update_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.patch(
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )

    data, _ = await assert_status(response, expected_status_code=expected.ok)

    assert ProjectMetadataGet.model_validate(data).custom == custom_metadata

    # delete project
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])
    response = await client.delete(f"{url}")
    await assert_status(response, expected_status_code=expected.no_content)

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
    await assert_status(response, expected_status_code=expected.not_found)


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_project_with_parent_project_node(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    aiopg_engine: aiopg.sa.Engine,
):
    """this is new way of setting parents by using request headers"""
    catalog_subsystem_mock([user_project])
    parent_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
    )
    assert parent_project

    parent_project_uuid = TypeAdapter(ProjectID).validate_python(parent_project["uuid"])
    parent_node_id = TypeAdapter(NodeID).validate_python(
        random.choice(list(parent_project["workbench"]))  # noqa: S311
    )
    child_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )
    assert child_project
    async with aiopg_engine.acquire() as connection:
        project_db_metadata = await get_db_project_metadata(
            connection, child_project["uuid"]
        )
        assert project_db_metadata.parent_project_uuid == parent_project_uuid
        assert project_db_metadata.parent_node_id == parent_node_id

    # now we set the metadata with another node_id which shall not override the already set genealogy
    another_node_id = random.choice(  # noqa: S311
        [n for n in parent_project["workbench"] if NodeID(n) != parent_node_id]
    )
    assert NodeID(another_node_id) != parent_node_id
    custom_metadata = {
        "number": 3.14,
        "string": "str",
        "boolean": False,
        "node_id": f"{another_node_id}",
    }
    assert client.app
    url = client.app.router["update_project_metadata"].url_for(
        project_id=child_project["uuid"]
    )
    response = await client.patch(
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )
    data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
    assert ProjectMetadataGet.model_validate(data).custom == custom_metadata
    # check child project has parent unchanged
    async with aiopg_engine.acquire() as connection:
        project_db_metadata = await get_db_project_metadata(
            connection, child_project["uuid"]
        )
        assert project_db_metadata.parent_project_uuid == parent_project_uuid
        assert project_db_metadata.parent_node_id == parent_node_id


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_project_with_invalid_parent_project_node(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    aiopg_engine: aiopg.sa.Engine,
    faker: Faker,
):
    """this is new way of setting parents by using request headers"""
    catalog_subsystem_mock([user_project])
    parent_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
    )
    assert parent_project

    parent_project_uuid = TypeAdapter(ProjectID).validate_python(parent_project["uuid"])
    parent_node_id = TypeAdapter(NodeID).validate_python(
        random.choice(list(parent_project["workbench"]))  # noqa: S311
    )

    # creating with random project UUID should fail
    random_project_uuid = TypeAdapter(ProjectID).validate_python(faker.uuid4())
    child_project = await request_create_project(
        client,
        expected.accepted,
        expected.not_found,
        logged_user,
        primary_group,
        parent_project_uuid=random_project_uuid,
        parent_node_id=parent_node_id,
    )
    assert not child_project

    # creating with a random node ID should fail too
    random_node_id = TypeAdapter(NodeID).validate_python(faker.uuid4())
    child_project = await request_create_project(
        client,
        expected.accepted,
        expected.not_found,
        logged_user,
        primary_group,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=random_node_id,
    )
    assert not child_project

    # creating with only a parent project ID should fail too
    child_project = await request_create_project(
        client,
        expected.unprocessable,
        expected.unprocessable,
        logged_user,
        primary_group,
        parent_project_uuid=parent_project_uuid,
    )
    assert not child_project

    # creating with only a parent node ID should fail too
    random_node_id = TypeAdapter(NodeID).validate_python(faker.uuid4())
    child_project = await request_create_project(
        client,
        expected.unprocessable,
        expected.unprocessable,
        logged_user,
        primary_group,
        parent_node_id=parent_node_id,
    )
    assert not child_project


@pytest.mark.parametrize(*standard_user_role_response())
async def test_set_project_parent_backward_compatibility(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    expected: ExpectedResponse,
    aiopg_engine: aiopg.sa.Engine,
):
    """backwards compatiblity with sim4life.io runs like so
    - create a project
    - pass project metadata with a node_id inside
    - osparc will try to find the project id and set it as parent
    """
    assert client.app

    # create a blank project (no nodes necessary)
    child_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        project={"name": "child"},
    )

    # create a parent project with nodes
    parent_project = user_project

    # create some custom data with one of parents node_id as creator
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
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )
    data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
    assert ProjectMetadataGet.model_validate(data).custom == custom_metadata
    # check child project has parent set correctly
    async with aiopg_engine.acquire() as connection:
        project_db_metadata = await get_db_project_metadata(
            connection, child_project["uuid"]
        )
        assert project_db_metadata.parent_project_uuid == ProjectID(
            parent_project["uuid"]
        )
        assert f"{project_db_metadata.parent_node_id}" in parent_project["workbench"]


@pytest.mark.parametrize(*standard_user_role_response())
async def test_update_project_metadata_backward_compatibility_with_same_project_does_not_raises_and_does_not_work(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    aiopg_engine: aiopg.sa.Engine,
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
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )
    await assert_status(response, expected_status_code=expected.ok)

    # using one of its own nodes as parent is not allowed
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
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )
    await assert_status(response, expected_status_code=expected.ok)

    # check project has no parent
    async with aiopg_engine.acquire() as connection:
        project_db_metadata = await get_db_project_metadata(
            connection, child_project["uuid"]
        )
        assert project_db_metadata.parent_project_uuid is None
        assert project_db_metadata.parent_node_id is None


@pytest.mark.parametrize(*standard_user_role_response())
async def test_update_project_metadata_s4lacad_backward_compatibility_passing_nil_parent_node_id(
    # for deletion
    mocked_director_v2_api: None,
    storage_subsystem_mock: MockedStorageSubsystem,
    #
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    expected: ExpectedResponse,
    aiopg_engine: aiopg.sa.Engine,
):
    assert client.app

    child_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
    )

    # set metadata with node_id set to UUID(0), which should not raise
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
        f"{url}", json=ProjectMetadataUpdate(custom=custom_metadata).model_dump()
    )
    data, _ = await assert_status(response, expected_status_code=status.HTTP_200_OK)
    assert ProjectMetadataGet.model_validate(data).custom == custom_metadata

    # check project has no parent
    async with aiopg_engine.acquire() as connection:
        project_db_metadata = await get_db_project_metadata(
            connection, child_project["uuid"]
        )
        assert project_db_metadata.parent_project_uuid is None
        assert project_db_metadata.parent_node_id is None
