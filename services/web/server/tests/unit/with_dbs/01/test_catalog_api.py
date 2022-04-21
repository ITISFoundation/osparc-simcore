# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Type

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import NewProject
from simcore_service_webserver.application import (
    create_safe_application,
    setup_catalog,
    setup_db,
    setup_login,
    setup_products,
    setup_projects,
    setup_rest,
    setup_security,
    setup_session,
)
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.catalog_settings import (
    CatalogSettings,
    get_plugin_settings,
)
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.log import setup_logging


@pytest.fixture
def app_cfg(default_app_cfg: ConfigDict, unused_tcp_port_factory: Callable):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = unused_tcp_port_factory()
    cfg["storage"]["port"] = unused_tcp_port_factory()

    exclude = {
        "tracing",
        "director",
        "smtp",
        "storage",
        "activity",
        "diagnostics",
        "groups",
        "tags",
        "publications",
        "computation",
        "clusters",
        "socketio",
        "studies_dispatcher",
    }
    include = {
        "db",
        "rest",
        "catalog",
        "projects",
        "products",
        "login",
        "users",
        "resource_manager",
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg


@pytest.fixture()
def client(
    event_loop,
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
    setup_projects(app)
    setup_products(app)

    yield event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": app_cfg["main"]["port"]})
    )


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


@pytest.fixture
async def user_project(
    client,
    fake_project,
    logged_user,
    tests_data_dir: Path,
):
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


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
    user_project: dict[str, Any],
    mock_catalog_service_api_responses,
    expected: Type[web.HTTPException],
):
    assert client.app
    assert client.app.router
    url = client.app.router["get_node_resources"].url_for(
        project_id=user_project["uuid"], node_id="5739e377-17f7-4f09-a6ad-62659fb7fdec"
    )
    resp = await client.get(f"{url}")
    data, errors = await assert_status(resp, expected)
