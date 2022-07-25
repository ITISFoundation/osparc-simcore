# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from typing import Any
from uuid import uuid4

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from settings_library.catalog import CatalogSettings
from simcore_service_webserver.catalog_settings import get_plugin_settings
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects.project_models import ProjectDict


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
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_node_resources(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    mock_catalog_service_api_responses: None,
    expected: type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["get_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.get(f"{url}")
        await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_wrong_project_raises_not_found_error(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["get_node_resources"].url_for(
            project_id=f"{uuid4()}", node_id=node_id
        )
        response = await client.get(f"{url}")
        await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_wrong_node_raises_not_found_error(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    url = client.app.router["get_node_resources"].url_for(
        project_id=user_project["uuid"], node_id=f"{uuid4()}"
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPNotImplemented),
    ],
)
async def test_replace_node_resources(
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


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
):
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {
        "service_key": faker.pystr(),
        "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}",
        "service_id": None,
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.created)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node_returns_422_if_body_is_missing(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
):
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    for partial_body in [
        {},
        {"service_key": faker.pystr()},
        {
            "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}"
        },
    ]:
        response = await client.post(url.path, json=partial_body)
        await assert_status(response, expected.unprocessable)
