# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
from typing import Callable

import pytest
from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.application import (
    create_safe_application,
    setup_catalog,
    setup_db,
    setup_login,
    setup_products,
    setup_rest,
    setup_security,
    setup_session,
)
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.catalog_client import KCATALOG_ORIGIN
from simcore_service_webserver.db_models import UserRole


@pytest.fixture()
def client(
    loop,
    app_cfg,
    aiohttp_client,
    postgres_db,
    monkeypatch_setenv_from_app_config: Callable,
):
    # fixture: minimal client with catalog-subsystem enabled and
    #   only pertinent modules
    #
    # - Mocks calls to actual API

    monkeypatch_setenv_from_app_config(app_cfg)
    app = create_safe_application(app_cfg)
    assert setup_settings(app)

    # patch all
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    assert setup_catalog(app)
    setup_products(app)

    yield loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": app_cfg["main"]["port"]})
    )


@pytest.fixture
def mock_catalog_service_api_responses(client, aioresponses_mocker):
    origin = client.app[KCATALOG_ORIGIN]

    url_pattern = re.compile(f"^{origin}+/.*$")

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
    client,
    logged_user,
    api_version_prefix,
    mock_catalog_service_api_responses,
    expected,
):
    VTAG = api_version_prefix

    # list resources
    assert client.app.router

    def assert_route(name, expected_url, **kargs):
        url = client.app.router[name].url_for(**{k: str(v) for k, v in kargs.items()})
        assert str(url) == expected_url
        return url

    url = assert_route("list_catalog_dags", f"/{VTAG}/catalog/dags")
    resp = await client.get(url)
    data, errors = await assert_status(resp, expected)

    # create resource
    url = assert_route("create_catalog_dag", f"/{VTAG}/catalog/dags")
    data = {}  # TODO: some fake data
    resp = await client.post(url, json=data)
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
    resp = await client.put(url, json=new_data)
    data, errors = await assert_status(resp, expected)

    # TODO: update resource
    # patch_data = {} # TODO: some patch fake
    # res = await client.patch(f"/{VTAG}/dags/{dag_id}", json=patch_data)
    # data, errors = await assert_status(resp, expected)

    # delete
    url = assert_route(
        "delete_catalog_dag", f"/{VTAG}/catalog/dags/{dag_id}", dag_id=dag_id
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, expected)
