# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections import UserDict
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest import mock
from uuid import UUID, uuid4

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    standard_role_response,
)
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
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
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
async def test_create_node_properly_upgrade_database(
    client: TestClient,
    logged_user: UserDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    catalog_subsystem_mock,
    mocker: MockerFixture,
):
    create_or_update_mock = mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        autospec=True,
        return_value=None,
    )

    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])

    # Use-case 1.: not passing a service UUID will generate a new one on the fly
    body = {
        "service_key": f"simcore/services/frontend/{faker.pystr()}",
        "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}",
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.created)
    if not error:
        assert data
        assert "node_id" in data
        assert UUID(data["node_id"])
        new_node_uuid = UUID(data["node_id"])
        expected_project_data = deepcopy(user_project)
        expected_project_data["workbench"][f"{new_node_uuid}"] = {
            "key": body["service_key"],
            "version": body["service_version"],
        }
        # give access to services inside the project
        catalog_subsystem_mock([expected_project_data])
        # check the project was updated
        get_url = client.app.router["get_project"].url_for(
            project_id=user_project["uuid"]
        )
        response = await client.get(get_url.path)
        prj_data, error = await assert_status(response, expected.ok)
        assert prj_data
        assert not error
        assert "workbench" in prj_data
        assert (
            f"{new_node_uuid}" in prj_data["workbench"]
        ), f"node {new_node_uuid} is missing from project workbench! workbench nodes {list(prj_data['workbench'].keys())}"

        create_or_update_mock.assert_called_once_with(
            mock.ANY, logged_user["id"], user_project["uuid"]
        )

    # this does not start anything in the backend since this is not a dynamic service
    mocked_director_v2_api["director_v2_api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node_returns_422_if_body_is_missing(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
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
        assert response.status == expected.unprocessable.status_code
    # this does not start anything in the backend
    mocked_director_v2_api["director_v2_api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(
    "node_class, expect_run_service_call",
    [("dynamic", True), ("comp", False), ("frontend", False)],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node(
    node_class: str,
    expect_run_service_call: bool,
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mocker: MockerFixture,
):
    create_or_update_mock = mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        autospec=True,
        return_value=None,
    )

    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])

    # Use-case 1.: not passing a service UUID will generate a new one on the fly
    body = {
        "service_key": f"simcore/services/{node_class}/{faker.pystr()}",
        "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}",
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.created)
    if data:
        assert not error
        create_or_update_mock.assert_called_once()
        if expect_run_service_call:
            mocked_director_v2_api[
                "director_v2_api.run_dynamic_service"
            ].assert_called_once()
        else:
            mocked_director_v2_api[
                "director_v2_api.run_dynamic_service"
            ].assert_not_called()
    else:
        assert error


@pytest.mark.parametrize(
    "node_class",
    [("dynamic"), ("comp"), ("frontend")],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_creating_deprecated_node_returns_406_not_acceptable(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    node_class: str,
):
    mock_catalog_api["get_service"].return_value["deprecated"] = (
        datetime.utcnow() - timedelta(days=1)
    ).isoformat()
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])

    # Use-case 1.: not passing a service UUID will generate a new one on the fly
    body = {
        "service_key": f"simcore/services/{node_class}/{faker.pystr()}",
        "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}",
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.not_acceptable)
    assert error
    assert not data
    # this does not start anything in the backend since this node is deprecated
    mocked_director_v2_api["director_v2_api.run_dynamic_service"].assert_not_called()
