# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
from pathlib import Path
from typing import Any, Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import assert_get_same_project
from simcore_service_webserver.db_models import UserRole


@pytest.fixture
def test_tags_data(fake_data_dir: Path) -> dict[str, Any]:
    with (fake_data_dir / "test_tags_data.json").open() as fp:
        return json.load(fp).get("added_tags")


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_tags_to_studies(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project,
    expected: web.HTTPException,
    test_tags_data: dict[str, Any],
    catalog_subsystem_mock: Callable,
):
    catalog_subsystem_mock([user_project])

    # Add test tags
    tags = test_tags_data
    added_tags = []

    for tag in tags:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(url, json=tag)
        added_tag, _ = await assert_status(resp, expected)
        added_tags.append(added_tag)

        # Add tag to study
        url = client.app.router["add_tag"].url_for(
            study_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.put(url)
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
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)

    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_tag"].url_for(
        study_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.delete(url)
    await assert_status(resp, expected)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)
