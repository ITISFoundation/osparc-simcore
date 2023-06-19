# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole

API_PREFIX = "/" + api_version_prefix


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, web.HTTPOk),
    ],
)
async def test_project_comments(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    template_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    base_url = client.app.router["list_project_comments"].url_for(
        project_uuid=user_project["uuid"]
    )
    resp = await client.get(base_url)
    data = await resp.json()
    assert resp.status == 200
    assert data["data"] == []

    # Now we will add first comment
    body = {"content": "My first comment", "user_id": logged_user["id"]}
    resp = await client.post(base_url, json=body)
    assert resp.status == 201

    # Now we will add second comment
    resp = await client.post(
        base_url, json={"content": "My second comment", "user_id": logged_user["id"]}
    )
    assert resp.status == 201
    data = await resp.json()
    comment_id = data["data"]

    # Now we will list all comments for the project
    resp = await client.get(base_url)
    data = await resp.json()
    assert resp.status == 200
    assert len(data["data"]) == 2

    # Now we will update the second comment
    updated_comment = "Updated second comment"
    resp = await client.put(
        base_url / f"{comment_id}",
        json={"content": updated_comment, "user_id": logged_user["id"]},
    )
    data = await resp.json()
    assert resp.status == 200
    assert data["data"]["content"] == updated_comment

    # Now we will get the second comment
    resp = await client.get(base_url / f"{comment_id}")
    data = await resp.json()
    assert resp.status == 200
    assert data["data"]["content"] == updated_comment

    # Now we will delete the second comment
    resp = await client.delete(base_url / f"{comment_id}")
    data = await resp.json()
    assert resp.status == 204

    # Now we will list all comments for the project
    resp = await client.get(base_url)
    data = await resp.json()
    assert resp.status == 200
    assert len(data["data"]) == 1
