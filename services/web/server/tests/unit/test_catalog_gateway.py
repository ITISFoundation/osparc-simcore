# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp import web
from yarl import URL

from simcore_service_webserver.application import create_safe_application
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.catalog_config import schema as catalog_schema


@pytest.fixture()
async def client(loop, aiohttp_client, aiohttp_server, monkeypatch):
    # fixture: minimal client with catalog-subsystem enabled and
    #   only pertinent modules
    #
    # - Mocks calls to actual API
    app_cfg = {}

    app = create_application(app_cfg)

    # patch all

    assert setup_catalog(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={'port':app_cfg["main"]["port"])}))




async def test_dag_resource(client, api_version_prefix):
    vx = api_version_prefix

    # list resources
    res = await client.get(f"/{vx}/dags")


    # create resource
    res = await client.post(f"/{vx}/dags")

    # list again
    res = await client.get(f"/{vx}/dags")


    # get resource
    dag_id = 0
    res = await client.post(f"/{vx}/dags/{dag_id}")

    # replace resource
    new_data = {}
    res = await client.put(f"/{vx}/dags/{dag_id}", json=new_data)

    # update resource
    patch_data = {}
    res = await client.patch(f"/{vx}/dags/{dag_id}", json=patch_data)

    # delete
    res = await client.delete(f"/{vx}/dags/{dag_id}")
