# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import urllib.parse

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from settings_library.catalog import CatalogSettings
from simcore_service_webserver.catalog.settings import get_plugin_settings
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def mock_catalog_service_api_responses(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: CatalogSettings = get_plugin_settings(client.app)

    url_pattern = re.compile(f"^{settings.base_url}+/.+$")

    service_resources = parse_obj_as(
        ServiceResourcesDict,
        ServiceResourcesDictHelpers.Config.schema_extra["examples"][0],
    )
    jsonable_service_resources = ServiceResourcesDictHelpers.create_jsonable(
        service_resources
    )

    aioresponses_mocker.get(url_pattern, payload=jsonable_service_resources)
    aioresponses_mocker.post(url_pattern, payload=jsonable_service_resources)
    aioresponses_mocker.put(url_pattern, payload=jsonable_service_resources)
    aioresponses_mocker.patch(url_pattern, payload=jsonable_service_resources)
    aioresponses_mocker.delete(url_pattern)

    return aioresponses_mocker


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_service_resources(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses: AioResponsesMock,
    expected: type[web.HTTPException],
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources_handler"].url_for(
        service_key=urllib.parse.quote("simcore/services/dynamic/someservice", safe=""),
        service_version="3.4.5",
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected)


@pytest.fixture
def mock_catalog_service_api_responses_not_found(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: CatalogSettings = get_plugin_settings(client.app)
    url_pattern = re.compile(f"^{settings.base_url}+/.*$")

    aioresponses_mocker.get(url_pattern, exception=web.HTTPNotFound)
    return aioresponses_mocker


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_undefined_service_resources_raises_not_found_error(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses_not_found: AioResponsesMock,
    expected: type[web.HTTPException],
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources_handler"].url_for(
        service_key="simcore%2Fservices%2Fdynamic%2Fsomeservice",
        service_version="3.4.5",
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected)
