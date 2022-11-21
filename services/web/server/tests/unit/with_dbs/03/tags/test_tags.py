# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import assert_get_same_project
from simcore_service_webserver import tags_handlers
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.tags_handlers import TagGet


@pytest.mark.parametrize(
    "route",
    tags_handlers.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_tags_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{api_version_prefix}")
    path = route.path.replace(f"/{api_version_prefix}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"


@pytest.fixture
def fake_tags(faker: Faker) -> list[dict[str, Any]]:
    return [
        {"name": "tag1", "description": "description1", "color": "#f00"},
        {"name": "tag2", "description": "description2", "color": "#00f"},
    ]


# TODO: extend tests to other roles
@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_tags_to_studies(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project,
    expected: type[web.HTTPException],
    fake_tags: dict[str, Any],
    catalog_subsystem_mock: Callable,
):
    catalog_subsystem_mock([user_project])
    assert client.app

    # Add test tags
    added_tags = []

    for tag in fake_tags:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(f"{url}", json=tag)
        added_tag, _ = await assert_status(resp, expected)
        added_tags.append(added_tag)

        # Add tag to study
        url = client.app.router["add_tag"].url_for(
            study_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.put(f"{url}")
        data, _ = await assert_status(resp, expected)

        # Tag is included in response
        assert added_tag["id"] in data["tags"]

    # check the tags are in
    user_project["tags"] = [tag["id"] for tag in added_tags]
    user_project["state"] = jsonable_encoder(
        ProjectState(
            locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
            state=ProjectRunningState(value=RunningState.UNKNOWN),
        ),
        exclude_unset=True,
    )
    data = await assert_get_same_project(client, user_project, expected)

    # Delete tag0
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[0].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, web.HTTPNoContent)

    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_tag"].url_for(
        study_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.delete(f"{url}")
    await assert_status(resp, expected)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, web.HTTPNoContent)


@pytest.mark.skip(reason="UNDER DEV")
async def test_list_tags_with_access_info(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
):
    assert client.app

    assert user_role == UserRole.USER

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert parse_obj_as(data, list[TagGet])
