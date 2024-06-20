# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import urllib.parse
from http import HTTPStatus

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_catalog.services import ServiceUpdate
from models_library.api_schemas_webserver.catalog import DEVServiceGet
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
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


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_dev_list_get_update_services(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses: AioResponsesMock,
):
    assert client.app
    assert client.app.router

    # LIST latest
    url = client.app.router["dev_list_services_latest"].url_for()
    assert url.path.endswith("/catalog/services/-/latest")

    response = await client.get(
        f"{url}",
    )
    await assert_status(response, status.HTTP_200_OK)

    # GET
    service_key = "simcore/services/dynamic/someservice"
    service_version = "3.4.5"

    url = client.app.router["dev_get_service"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )
    response = await client.get(
        f"{url}",
    )
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert data
    assert error is None
    model = parse_obj_as(DEVServiceGet, data)
    assert model.key == service_key
    assert model.version == service_version

    # PATCH
    update = ServiceUpdate(name="foo", thumbnail=None, description="bar")
    response = await client.patch(
        f"{url}", json=jsonable_encoder(update, exclude_unset=True)
    )

    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert error is None
    model = parse_obj_as(DEVServiceGet, data)
    assert model.key == service_key
    assert model.version == service_version
    assert model.name == "foo"
    assert model.description == "bar"
