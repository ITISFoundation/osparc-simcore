# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.client_session import APP_CLIENT_SESSION_KEY
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.catalog import (
    is_service_responsive,
    setup_catalog,
    to_backend_service,
)
from simcore_service_webserver.rest import APP_OPENAPI_SPECS_KEY, load_openapi_specs
from yarl import URL


@pytest.fixture
def client(loop, aiohttp_client: TestClient):
    app = create_safe_application()

    app[APP_OPENAPI_SPECS_KEY] = load_openapi_specs()
    setup_catalog.__wrapped__(app)

    yield loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def mock_api_calls_to_catalog(client, mocker):
    raise NotImplementedError("TODO: Use aioresponse to emulate catalog responses")


# TESTS -------------------------------------------------------------------


def test_url_translation():
    front_url = URL(
        f"https://osparc.io/{api_version_prefix}/catalog/dags/123?page_size=6"
    )

    rel_url = front_url.relative()
    assert rel_url.path.startswith(f"/{api_version_prefix}/catalog")

    api_target_origin = URL("http://catalog:8000")
    api_target_url = to_backend_service(rel_url, api_target_origin, "v5")

    assert str(api_target_url) == "http://catalog:8000/v5/dags/123?page_size=6"


def test_catalog_routing(client):
    assert any(client.app.router.resources()), "No routes detected?"

    for resource in client.app.router.resources():
        assert resource.canonical.startswith(f"/{api_version_prefix}/catalog")


# TODO: auto-create calls from openapi specs together with expected responses
# TODO: this test shall simply check that Web API calls are redirected correctly
@pytest.mark.skip(reason="DEV")
async def test_catalog_api_calls(client, mock_api_calls_to_catalog):
    client_session = client.app[APP_CLIENT_SESSION_KEY]

    assert await is_service_responsive(client.app)
    mock_api_calls_to_catalog.assert_called_once()

    # from .login.decorators import login_required
    v = api_version_prefix

    # create resource
    data = {}  # TODO: some fake data
    res = await client.post(f"/{v}/catalog/dags", json=data)
    assert res.status == 201

    # list resources
    res = await client.get(f"/{v}/catalog/dags")
    assert res.status == 200

    # get resource
    dag_id = 0
    res = await client.get(f"/{v}/catalog/dags/{dag_id}")
    assert res.status == 200

    # replace resource
    new_data = {}  # TODO: some fake data
    res = await client.put(f"/{v}/dags/{dag_id}", json=new_data)
    assert res.status == 200

    # update resource
    patch_data = {}  # TODO: some patch fake
    res = await client.patch(f"/{v}/dags/{dag_id}", json=patch_data)
    assert res.status == 200

    # delete
    res = await client.delete(f"/{v}/dags/{dag_id}")
    assert res.status == 204
