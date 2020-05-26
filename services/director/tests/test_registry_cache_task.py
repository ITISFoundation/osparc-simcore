# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from asyncio import sleep

import pytest

from simcore_service_director import config, main, registry_cache_task, registry_proxy


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    aiohttp_unused_port,
    configure_schemas_location,
    configure_registry_access,
):
    config.DIRECTOR_REGISTRY_CACHING = True
    config.DIRECTOR_REGISTRY_CACHING_TTL = 5
    # config.DIRECTOR_REGISTRY_CACHING_TTL = 5
    app = main.setup_app()
    server_kwargs = {"port": aiohttp_unused_port(), "host": "localhost"}

    registry_cache_task.setup(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs=server_kwargs))


async def test_registry_caching_task(loop, client, push_services):
    app = client.app
    assert app

    # check the task is started
    assert registry_cache_task.TASK_NAME in app
    # check the registry cache is empty (no calls yet)
    assert registry_cache_task.APP_REGISTRY_CACHE_DATA_KEY in app

    # check we do not get any repository
    list_of_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.ALL
    )
    assert not list_of_services
    assert app[registry_cache_task.APP_REGISTRY_CACHE_DATA_KEY] != {}
    # create services in the registry
    pushed_services = push_services(
        number_of_computational_services=1, number_of_interactive_services=1
    )
    # the services shall be updated
    await sleep(
        config.DIRECTOR_REGISTRY_CACHING_TTL * 1.1
    )  # NOTE: this can take some time. Sleep increased by 10%.
    list_of_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.ALL
    )
    assert len(list_of_services) == 2
    # add more
    pushed_services = push_services(
        number_of_computational_services=2,
        number_of_interactive_services=2,
        version="2.0.",
    )
    await sleep(
        config.DIRECTOR_REGISTRY_CACHING_TTL * 1.1
    )  # NOTE: this sometimes takes a bit more. Sleep increased a 10%.
    list_of_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.ALL
    )
    assert len(list_of_services) == len(pushed_services)
