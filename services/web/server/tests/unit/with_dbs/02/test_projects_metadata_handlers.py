# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
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
    url = client.app.router["get_project_custom_metadata"].url_for(
        project_id=faker.uuid4()
    )
    response = await client.get(f"{url}")

    await assert_status(response, expected_cls=web.HTTPNotFound)

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
    response = await client.put(f"{url}", json=custom_metadata)

    data, _ = await assert_status(response, expected_cls=web.HTTPOk)
    assert data["metadata"] == custom_metadata

    # delete project
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])
    response = await client.delete(f"{url}", json=custom_metadata)
    await assert_status(response, expected_cls=web.HTTPNoContent)

    # no metadata -> project not foun d
    url = client.app.router["get_project_custom_metadata"].url_for(
        project_id=user_project["uuid"]
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected_cls=web.HTTPNotFound)
    await assert_status(response, expected_cls=web.HTTPNotFound)
