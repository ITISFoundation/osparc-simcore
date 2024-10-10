# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import urllib.parse
from http import HTTPStatus

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import TypeAdapter
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
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

    service_resources = TypeAdapter(ServiceResourcesDict).validate_python(
        ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],
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
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_service_resources(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses: AioResponsesMock,
    expected: HTTPStatus,
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources"].url_for(
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
        (UserRole.TESTER, status.HTTP_404_NOT_FOUND),
    ],
)
async def test_get_undefined_service_resources_raises_not_found_error(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses_not_found: AioResponsesMock,
    expected: HTTPStatus,
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources"].url_for(
        service_key="simcore%2Fservices%2Fdynamic%2Fsomeservice",
        service_version="3.4.5",
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected)
