# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import Mock

import pytest
import toolz
from aiocache import SimpleMemoryCache  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException, status
from models_library.function_services_catalog.api import is_function_service
from models_library.services_metadata_published import ServiceMetaDataPublished
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from redis.exceptions import ConnectionError as RedisConnectionError
from respx.router import MockRouter
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient
from simcore_service_catalog.service import manifest
from simcore_service_catalog.service.manifest_cache import create_service_manifest_cache

pytest_simcore_core_services_selection = ["redis"]


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
    background_task_lifespan_disabled: None,
    repository_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
) -> DirectorClient:
    _client = get_director_client(app)
    assert app.state.director_api == _client
    assert isinstance(_client, DirectorClient)
    return _client


@pytest.fixture
async def all_services_map(
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
) -> manifest.ServiceMetaDataPublishedDict:
    return await manifest.get_services_map(director_client, service_manifest_cache)


@pytest.fixture
async def service_manifest_cache() -> AsyncIterator[BaseCache]:
    cache = SimpleMemoryCache(serializer=JsonSerializer())
    try:
        yield cache
    finally:
        await cache.close()


async def test_get_services_map(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
):
    all_services_map = await manifest.get_services_map(director_client, service_manifest_cache)
    assert mocked_director_rest_api["list_services"].called

    for service in all_services_map.values():
        if is_function_service(service.key):
            assert service.image_digest is None
        else:
            assert service.image_digest is not None

    services_image_digest = {s.image_digest for s in all_services_map.values() if s.image_digest}
    assert len(services_image_digest) < len(all_services_map)


async def test_get_services_map_succeeds_when_cache_is_unavailable(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
):
    unavailable_cache = Mock(spec=BaseCache)
    unavailable_cache.multi_set.side_effect = RedisConnectionError("Redis is unavailable")

    all_services_map = await manifest.get_services_map(director_client, unavailable_cache)

    assert all_services_map
    assert mocked_director_rest_api["list_services"].call_count == 1


async def test_get_service(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_service in all_services_map.values():
        service = await manifest.get_service(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_client,
            service_cache=service_manifest_cache,
        )

        assert service == expected_service

    assert not mocked_director_rest_api["get_service"].called


async def test_get_service_cache_miss_calls_director_then_caches(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    expected_service = next(service for service in all_services_map.values() if not is_function_service(service.key))
    assert await service_manifest_cache.clear()

    for _ in range(2):
        service = await manifest.get_service(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_client,
            service_cache=service_manifest_cache,
        )
        assert service == expected_service

    assert mocked_director_rest_api["get_service"].call_count == 1


async def test_get_service_falls_back_to_director_when_cache_is_unavailable(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    expected_service = next(service for service in all_services_map.values() if not is_function_service(service.key))
    unavailable_cache = Mock(spec=BaseCache)
    unavailable_cache.get.side_effect = RedisConnectionError("Redis is unavailable")
    unavailable_cache.set.side_effect = RedisConnectionError("Redis is unavailable")

    service = await manifest.get_service(
        key=expected_service.key,
        version=expected_service.version,
        director_client=director_client,
        service_cache=unavailable_cache,
    )

    assert service == expected_service
    assert mocked_director_rest_api["get_service"].call_count == 1


async def test_get_service_recovers_from_invalid_cache_entry(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    expected_service = next(service for service in all_services_map.values() if not is_function_service(service.key))
    cache_key = manifest._build_service_cache_key(key=expected_service.key, version=expected_service.version)
    assert await service_manifest_cache.set(cache_key, {"key": expected_service.key})

    service = await manifest.get_service(
        key=expected_service.key,
        version=expected_service.version,
        director_client=director_client,
        service_cache=service_manifest_cache,
    )

    assert service == expected_service
    assert mocked_director_rest_api["get_service"].call_count == 1


async def test_get_batch_services_recovers_from_invalid_cache_entry(
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    expected_service = next(service for service in all_services_map.values() if not is_function_service(service.key))
    cache_key = manifest._build_service_cache_key(key=expected_service.key, version=expected_service.version)
    assert await service_manifest_cache.set(cache_key, {"key": expected_service.key})

    got_services = await manifest.get_batch_services(
        [(expected_service.key, expected_service.version)],
        director_client,
        service_manifest_cache,
    )

    assert got_services == [expected_service]


async def test_get_service_ports(
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_service in all_services_map.values():
        ports = await manifest.get_service_ports(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_client,
            service_cache=service_manifest_cache,
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


async def test_get_batch_services_cold_cache_uses_single_director_request(
    expected_director_rest_api_list_services: list[dict[str, Any]],
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
):
    expected_services = [
        ServiceMetaDataPublished.model_validate(service) for service in expected_director_rest_api_list_services[:2]
    ]

    got_services = await manifest.get_batch_services(
        [(service.key, service.version) for service in expected_services],
        director_client,
        service_manifest_cache,
    )

    assert got_services == expected_services
    assert mocked_director_rest_api["list_services"].call_count == 1
    assert not mocked_director_rest_api["get_service"].called


async def test_get_batch_services_cold_cache_is_coalesced_across_replicas(
    expected_director_rest_api_list_services: list[dict[str, Any]],
    redis_settings: RedisSettings,
):
    caches = [create_service_manifest_cache(redis_settings) for _ in range(2)]
    await caches[0].clear()
    lock_client = RedisClientSDK(
        redis_settings.build_redis_dsn(RedisDatabase.LOCKS),
        client_name="catalog-manifest-cache-test",
    )
    await lock_client.setup()
    director_client = Mock(spec=DirectorClient)
    director_call_started = asyncio.Event()
    release_director_call = asyncio.Event()

    async def _list_services(path: str) -> list[dict[str, Any]]:
        assert path == "/services"
        director_call_started.set()
        await release_director_call.wait()
        return expected_director_rest_api_list_services

    director_client.get.side_effect = _list_services
    expected_service = ServiceMetaDataPublished.model_validate(expected_director_rest_api_list_services[0])
    selection = [(expected_service.key, expected_service.version)]

    try:
        first_request = asyncio.create_task(
            manifest.get_batch_services(selection, director_client, caches[0], lock_client=lock_client)
        )
        await director_call_started.wait()
        second_request = asyncio.create_task(
            manifest.get_batch_services(selection, director_client, caches[1], lock_client=lock_client)
        )
        release_director_call.set()

        assert await asyncio.gather(first_request, second_request) == [[expected_service], [expected_service]]
    finally:
        await asyncio.gather(*(cache.close() for cache in caches))
        await lock_client.shutdown()

    director_client.get.assert_awaited_once_with("/services")


async def test_get_batch_services_falls_back_to_director_when_cache_is_unavailable(
    expected_director_rest_api_list_services: list[dict[str, Any]],
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
):
    expected_services = [
        ServiceMetaDataPublished.model_validate(service) for service in expected_director_rest_api_list_services[:2]
    ]
    unavailable_cache = Mock(spec=BaseCache)
    unavailable_cache.multi_get.side_effect = RedisConnectionError("Redis is unavailable")
    unavailable_cache.multi_set.side_effect = RedisConnectionError("Redis is unavailable")

    got_services = await manifest.get_batch_services(
        [(service.key, service.version) for service in expected_services],
        director_client,
        unavailable_cache,
    )

    assert got_services == expected_services
    assert mocked_director_rest_api["list_services"].call_count == 1
    assert not mocked_director_rest_api["get_service"].called


async def test_get_batch_services_does_not_raise_when_cache_lock_and_director_are_unavailable():
    director_client = Mock(spec=DirectorClient)
    director_client.get.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    director_client.get_service.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    unavailable_cache = Mock(spec=BaseCache)
    unavailable_cache.multi_get.side_effect = RedisConnectionError("Redis is unavailable")
    unavailable_cache.get.side_effect = RedisConnectionError("Redis is unavailable")

    unavailable_lock_client = Mock(spec=RedisClientSDK)
    unavailable_lock_client.client_name = "catalog-manifest-cache-test"
    unavailable_lock_client.create_lock.side_effect = RedisConnectionError("Redis is unavailable")

    got_services = await manifest.get_batch_services(
        [("simcore/services/comp/itis/sleeper", "1.0.0")],
        director_client,
        unavailable_cache,
        lock_client=unavailable_lock_client,
    )

    assert [type(service) for service in got_services] == [HTTPException]


async def test_get_batch_services_empty_selection_skips_cache_and_director():
    director_client = Mock(spec=DirectorClient)
    service_manifest_cache = Mock(spec=BaseCache)

    assert await manifest.get_batch_services([], director_client, service_manifest_cache) == []
    assert not service_manifest_cache.multi_get.called


async def test_get_batch_services(
    mocked_director_rest_api: MockRouter,
    director_client: DirectorClient,
    service_manifest_cache: BaseCache,
    all_services_map: manifest.ServiceMetaDataPublishedDict,
):
    for expected_services in toolz.partition(2, all_services_map.values()):
        selection = [(s.key, s.version) for s in expected_services]
        got_services = await manifest.get_batch_services(
            selection,
            director_client,
            service_manifest_cache,
        )

        assert [(s.key, s.version) for s in got_services] == selection

        # NOTE: simpler to visualize
        for got, expected in zip(got_services, expected_services, strict=True):
            assert got == expected

    assert not mocked_director_rest_api["get_service"].called
