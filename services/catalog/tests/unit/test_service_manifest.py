# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio

import pytest
import toolz
from fastapi import FastAPI
from models_library.function_services_catalog.api import is_function_service
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog._constants import DEFAULT_DIRECTOR_BULK_FETCH_LEASE
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient
from simcore_service_catalog.service import manifest


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "SC_BOOT_MODE": "local-development",
        },
    )


@pytest.fixture
async def director_client(
    repository_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
) -> DirectorClient:
    _client = get_director_client(app)
    assert app.state.director_api == _client
    assert isinstance(_client, DirectorClient)

    # ensures manifest API caches are reset
    assert await manifest.get_service.cache.clear()
    assert await manifest._get_cached_services_map.cache.clear()  # noqa: SLF001

    return _client


@pytest.fixture
async def all_services_map(
    director_client: DirectorClient,
) -> manifest.ServiceMetaDataPublishedDict:
    return await manifest.get_services_map(director_client)


async def test_get_services_map(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
):
    all_services_map = await manifest.get_services_map(director_client)
    assert mocked_director_rest_api["list_services"].called

    for service in all_services_map.values():
        if is_function_service(service.key):
            assert service.image_digest is None
        else:
            assert service.image_digest is not None

    services_image_digest = {s.image_digest for s in all_services_map.values() if s.image_digest}
    assert len(services_image_digest) < len(all_services_map)


async def test_get_service(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_service in all_services_map.values():
        service = await manifest.get_service(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_client,
        )

        assert service == expected_service
        if not is_function_service(service.key):
            assert mocked_director_rest_api["get_service"].called


async def test_get_service_ports(
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_service in all_services_map.values():
        ports = await manifest.get_service_ports(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_client,
        )

        # Verify all ports are properly retrieved
        assert isinstance(ports, list)

        # Check input ports
        input_ports = [p for p in ports if p.kind == "input"]
        if expected_service.inputs:
            assert len(input_ports) == len(expected_service.inputs)
            for port in input_ports:
                assert port.key in expected_service.inputs
                assert port.port == expected_service.inputs[port.key]
        else:
            assert not input_ports

        # Check output ports
        output_ports = [p for p in ports if p.kind == "output"]
        if expected_service.outputs:
            assert len(output_ports) == len(expected_service.outputs)
            for port in output_ports:
                assert port.key in expected_service.outputs
                assert port.port == expected_service.outputs[port.key]
        else:
            assert not output_ports


async def test_get_batch_services(
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_services in toolz.partition(2, all_services_map.values()):
        selection = [(s.key, s.version) for s in expected_services]
        got_services = await manifest.get_batch_services(selection, director_client)

        assert [(s.key, s.version) for s in got_services] == selection

        # NOTE: simpler to visualize
        for got, expected in zip(got_services, expected_services, strict=True):
            assert got == expected


async def test_get_batch_services_uses_single_bulk_director_call(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    # a batch spanning several (non function) services
    selection = [(s.key, s.version) for s in all_services_map.values() if not is_function_service(s.key)]
    assert len(selection) > 1

    # NOTE: `all_services_map` fixture warms up the bulk fetch via `get_services_map`,
    # whereas `get_batch_services` goes through the cached `_get_cached_services_map`
    await manifest._get_cached_services_map.cache.clear()  # noqa: SLF001
    mocked_director_rest_api["list_services"].reset()
    mocked_director_rest_api["get_service"].reset()

    got_services = await manifest.get_batch_services(selection, director_client)

    assert [(s.key, s.version) for s in got_services] == selection

    # resolves the whole selection with a single bulk director call ...
    assert mocked_director_rest_api["list_services"].call_count == 1
    # ... and never fans out to the per-service endpoint
    assert not mocked_director_rest_api["get_service"].called


async def test_get_batch_services_coalesces_concurrent_cold_cache_calls(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    selection = [(s.key, s.version) for s in all_services_map.values() if not is_function_service(s.key)]
    assert len(selection) > 1

    # ensure a cold cache so all concurrent calls race on the populate step
    await manifest._get_cached_services_map.cache.clear()  # noqa: SLF001
    mocked_director_rest_api["list_services"].reset()
    mocked_director_rest_api["get_service"].reset()

    # a burst of concurrent callers on a cold cache
    results = await asyncio.gather(*(manifest.get_batch_services(selection, director_client) for _ in range(10)))

    for got_services in results:
        assert [(s.key, s.version) for s in got_services] == selection

    # the stampede lock collapses the burst into a single bulk director call
    assert mocked_director_rest_api["list_services"].call_count == 1
    assert not mocked_director_rest_api["get_service"].called


async def test_get_batch_services_when_director_slower_than_lease_keeps_results_correct(
    monkeypatch: pytest.MonkeyPatch,
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    # NOTE: documents the degraded behaviour when the director bulk fetch is slower than
    # the stampede `lease`. The lock expires mid-flight (RedLock lets every waiter pass
    # after `lease`), so request coalescing is defeated and each concurrent caller
    # re-issues its own fetch. The guarantee that must still hold is correctness: despite
    # the lost coalescing, every caller receives complete, correct results.
    selection = [(s.key, s.version) for s in all_services_map.values() if not is_function_service(s.key)]
    assert len(selection) > 1

    num_callers = 5
    release_director = asyncio.Event()
    all_callers_in_flight = asyncio.Event()
    call_count = 0

    async def _slow_get_services_map(_director_client: DirectorClient) -> manifest.ServiceMetaDataPublishedDict:
        nonlocal call_count
        call_count += 1
        if call_count == num_callers:
            # every caller has re-issued its own fetch (the lease expired for all waiters)
            all_callers_in_flight.set()
        # stays "in flight" until the test releases it, i.e. slower than the lease
        await release_director.wait()
        return all_services_map

    monkeypatch.setattr(manifest, "get_services_map", _slow_get_services_map)

    # a lease far shorter than the (blocked) director response time
    short_lease = 0.05
    manifest.set_services_cache_lease(short_lease)
    try:
        await manifest._get_cached_services_map.cache.clear()  # noqa: SLF001

        # a burst of concurrent callers racing on a cold cache
        callers = asyncio.gather(*(manifest.get_batch_services(selection, director_client) for _ in range(num_callers)))

        # wait until the lease has expired for every waiter so they have all re-issued
        # their own fetch (signalled by the slow fetch itself, no fixed sleep needed)
        async with asyncio.timeout(5):
            await all_callers_in_flight.wait()

        # all the in-flight fetches can now complete
        release_director.set()
        results = await callers

        # correctness is preserved for every caller despite the expired lease ...
        for got_services in results:
            assert [(s.key, s.version) for s in got_services] == selection

        # ... but the slow response defeated coalescing: every caller fetched on its own
        assert call_count == num_callers
    finally:
        manifest.set_services_cache_lease(30)  # restore the import-time default


async def test_get_batch_services_returns_keyerror_for_missing(
    director_client: DirectorClient,
):
    selection = [("simcore/services/comp/does-not-exist", "1.0.0")]

    got_services = await manifest.get_batch_services(selection, director_client)

    assert len(got_services) == 1
    assert isinstance(got_services[0], KeyError)


def test_set_services_cache_lease_reconfigures_both_caches():
    try:
        manifest.set_services_cache_lease(123)

        assert manifest._get_service_cache.lease == 123  # noqa: SLF001
        assert manifest._get_cached_services_map_cache.lease == 123  # noqa: SLF001
    finally:
        # restore the import-time default to keep other tests isolated
        manifest.set_services_cache_lease(DEFAULT_DIRECTOR_BULK_FETCH_LEASE)
