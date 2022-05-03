# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
from typing import Type

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

    aioresponses_mocker.get(url_pattern, payload={"data": {}})
    aioresponses_mocker.post(url_pattern, payload={"data": {}})
    aioresponses_mocker.put(url_pattern, payload={"data": {}})
    aioresponses_mocker.patch(url_pattern, payload={"data": {}})
    aioresponses_mocker.delete(url_pattern)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_dag_entrypoints(
    client: TestClient,
    logged_user: UserInfoDict,
    api_version_prefix: str,
    mock_catalog_service_api_responses: None,
    expected: Type[web.HTTPException],
):
    VTAG = api_version_prefix

    # list resources
    def assert_route(name, expected_url, **kargs):
        assert client.app
        assert client.app.router
        url = client.app.router[name].url_for(**{k: str(v) for k, v in kargs.items()})
        assert str(url) == expected_url
        return url

    url = assert_route("list_catalog_dags", f"/{VTAG}/catalog/dags")
    resp = await client.get(f"{url}")
    data, errors = await assert_status(resp, expected)

    # create resource
    url = assert_route("create_catalog_dag", f"/{VTAG}/catalog/dags")
    data = {}  # TODO: some fake data
    resp = await client.post(f"{url}", json=data)
    data, errors = await assert_status(resp, expected)

    # TODO: get resource
    # dag_id = 1
    # res = await client.get(f"/{VTAG}/catalog/dags/{dag_id}")
    # data, errors = await assert_status(resp, expected)

    # replace resource
    dag_id = 1
    new_data = {}  # TODO: some fake data

    url = assert_route(
        "replace_catalog_dag", f"/{VTAG}/catalog/dags/{dag_id}", dag_id=dag_id
    )
    resp = await client.put(f"{url}", json=new_data)
    data, errors = await assert_status(resp, expected)

    # TODO: update resource
    # patch_data = {} # TODO: some patch fake
    # res = await client.patch(f"/{VTAG}/dags/{dag_id}", json=patch_data)
    # data, errors = await assert_status(resp, expected)

    # delete
    url = assert_route(
        "delete_catalog_dag", f"/{VTAG}/catalog/dags/{dag_id}", dag_id=dag_id
    )
    resp = await client.delete(f"{url}")
    data, errors = await assert_status(resp, expected)


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
    mock_catalog_service_api_responses: None,
    expected: Type[web.HTTPException],
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources_handler"].url_for(
        service_key="some_service", service_version="3.4.5"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)


@pytest.fixture
def mock_catalog_service_api_responses_not_found(client, aioresponses_mocker):
    settings: CatalogSettings = get_plugin_settings(client.app)
    url_pattern = re.compile(f"^{settings.base_url}+/.*$")

    aioresponses_mocker.get(url_pattern, exception=web.HTTPNotFound)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_undefined_service_resources_raises_not_found_error(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_catalog_service_api_responses_not_found: None,
    expected: Type[web.HTTPException],
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_service_resources_handler"].url_for(
        service_key="some_service", service_version="3.4.5"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)
