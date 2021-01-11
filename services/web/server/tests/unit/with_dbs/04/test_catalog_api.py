# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy

import pytest
from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
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
from simcore_service_webserver.db_models import UserRole


@pytest.fixture()
def client(loop, app_cfg, aiohttp_client, postgres_db):
    # fixture: minimal client with catalog-subsystem enabled and
    #   only pertinent modules
    #
    # - Mocks calls to actual API

    cfg = deepcopy(app_cfg)

    cfg["catalog"]["enabled"] = True

    app = create_safe_application(app_cfg)

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
def patch_app_client_session(client, mocker):
    async def create_200_empty_response(*args, **kwargs):
        # Mocks aiohttp.ClientResponse
        # https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientResponse
        resp = mocker.MagicMock(name="SuccessfulEmptyResponse")

        resp.json = mocker.AsyncMock(return_value={})

        p = mocker.PropertyMock(return_value=200)
        type(resp).status = p
        return resp

    context_mock = mocker.Mock(name="Session Context Manager")
    context_mock.__aenter__ = mocker.AsyncMock(
        name="QueryResponse", side_effect=create_200_empty_response
    )
    context_mock.__aexit__ = mocker.AsyncMock(name="Exit", return_value=False)

    client_session = mocker.Mock()
    client_session.get.return_value = context_mock
    client_session.post.return_value = context_mock
    client_session.request.return_value = context_mock

    mocker.patch(
        "simcore_service_webserver.catalog.get_client_session",
        return_value=client_session,
    )


# TODO: with different user roles, i.e. access rights
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
    client, logged_user, api_version_prefix, patch_app_client_session, expected
):
    vx = api_version_prefix

    # list resources
    assert client.app.router

    def assert_route(name, expected_url, **kargs):
        url = client.app.router[name].url_for(**{k: str(v) for k, v in kargs.items()})
        assert str(url) == expected_url
        return url

    url = assert_route("list_catalog_dags", f"/{vx}/catalog/dags")
    resp = await client.get(url)
    data, errors = await assert_status(resp, expected)

    # create resource
    url = assert_route("create_catalog_dag", f"/{vx}/catalog/dags")
    data = {}  # TODO: some fake data
    resp = await client.post(url, json=data)
    data, errors = await assert_status(resp, expected)

    # TODO: get resource
    # dag_id = 1
    # res = await client.get(f"/{vx}/catalog/dags/{dag_id}")
    # data, errors = await assert_status(resp, expected)

    # replace resource
    dag_id = 1
    new_data = {}  # TODO: some fake data

    url = assert_route(
        "replace_catalog_dag", f"/{vx}/catalog/dags/{dag_id}", dag_id=dag_id
    )
    resp = await client.put(url, json=new_data)
    data, errors = await assert_status(resp, expected)

    # TODO: update resource
    # patch_data = {} # TODO: some patch fake
    # res = await client.patch(f"/{vx}/dags/{dag_id}", json=patch_data)
    # data, errors = await assert_status(resp, expected)

    # delete
    url = assert_route(
        "delete_catalog_dag", f"/{vx}/catalog/dags/{dag_id}", dag_id=dag_id
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, expected)
