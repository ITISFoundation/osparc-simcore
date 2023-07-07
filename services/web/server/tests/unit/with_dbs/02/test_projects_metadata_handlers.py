# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import MockedStorageSubsystem
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects import _crud_delete_utils
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

    _, error = await assert_status(response, expected_cls=web.HTTPNotFound)
    error_message = error["errors"][0]["message"]
    assert invalid_project_id in error_message
    assert "project" in error_message.lower()

    # get metadata of an existing project the first time -> empty {}
    url = client.app.router["get_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, expected_cls=web.HTTPOk)
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

    data, _ = await assert_status(response, expected_cls=web.HTTPOk)

    assert parse_obj_as(ProjectMetadataGet, data).custom == custom_metadata

    # delete project
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])
    response = await client.delete(f"{url}")
    await assert_status(response, expected_cls=web.HTTPNoContent)

    async def _wait_until_deleted():
        tasks = _crud_delete_utils.get_scheduled_tasks(
            project_uuid=user_project["uuid"], user_id=logged_user["id"]
        )
        await tasks[0]

    await _wait_until_deleted()

    # no metadata -> project not found
    url = client.app.router["get_project_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected_cls=web.HTTPNotFound)
