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
    ProjectCustomMetadataGet,
    ProjectCustomMetadataReplace,
)
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_custom_metadata_handlers(
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
    url = client.app.router["get_project_custom_metadata"].url_for(
        project_id=invalid_project_id
    )
    response = await client.get(f"{url}")

    _, error = await assert_status(response, expected_cls=web.HTTPNotFound)
    error_message = error["errors"][0]["message"]
    assert invalid_project_id in error_message
    assert "project" in error_message.lower()

    # get metadata of an existing project the first time -> empty {}
    url = client.app.router["get_project_custom_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, expected_cls=web.HTTPOk)
    assert data["metadata"] == {}

    # replace metadata
    custom_metadata = {"number": 3.14, "string": "str", "boolean": False}
    custom_metadata["other"] = json.dumps(custom_metadata)

    url = client.app.router["replace_project_custom_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.put(
        f"{url}", json=ProjectCustomMetadataReplace(metadata=custom_metadata).dict()
    )

    data, _ = await assert_status(response, expected_cls=web.HTTPOk)

    assert parse_obj_as(ProjectCustomMetadataGet, data).metadata == custom_metadata

    # delete project
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])
    response = await client.delete(f"{url}")
    await assert_status(response, expected_cls=web.HTTPNoContent)

    # no metadata -> project not foun d
    url = client.app.router["get_project_custom_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected_cls=web.HTTPNotFound)
