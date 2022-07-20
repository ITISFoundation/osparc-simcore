# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from typing import Any
from uuid import uuid3

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from settings_library.catalog import CatalogSettings
from simcore_service_webserver.catalog_settings import get_plugin_settings
from simcore_service_webserver.db_models import UserRole


@pytest.fixture
def mock_catalog_service_api_responses(client, aioresponses_mocker):
    settings: CatalogSettings = get_plugin_settings(client.app)
    url_pattern = re.compile(f"^{settings.base_url}+/.*$")

    aioresponses_mocker.get(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.post(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.put(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.patch(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.delete(
        url_pattern,
        repeat=True,
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPNotImplemented),
    ],
)
async def test_it(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    mock_catalog_service_api_responses: None,
    expected: type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(f"{url}", json={})
        await assert_status(response, expected)

    project_id = user_project["uuid"]
    node_id = list(project_workbench.keys())[0]

    # this is a node
    resp = await client.get(f"/v0/projects/{project_id}/nodes/{node_id}")

    # NOTE: it is i

    resp = await client.post(f"/v0/projects/{project_id}/nodes/{node_id}:start")

    #
    resp = await client.post(f"/v0/projects/{project_id}/dynamics/{node_id}:start")

    # option 2
    dynamics_id = uuid3(project_id, node_id)
    # PRO:
    # CONS: composes only in one direction! cannot deduce project_id and node_id from it
    await client.post(f"/v0/dynamics/{dynamics_id}:start")

    # option 3
    # PRO: composition based on
    node_name = f"projects/{project_id}/nodes/{node_id}"  # as name nodes
    await client.post(f"/v0/dynamics/{node_name}:start")
