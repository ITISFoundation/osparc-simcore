# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Type

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.db_models import UserRole


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_node_resources(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    expected: Type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["get_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.get(f"{url}")
        data, error = await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_replace_node_resources(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    expected: Type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(f"{url}", json={})
        data, error = await assert_status(response, expected)
