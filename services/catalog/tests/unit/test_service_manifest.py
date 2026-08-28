# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from unittest.mock import Mock

import pytest
import toolz
from aiocache import SimpleMemoryCache  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer  # type: ignore[import-untyped]
from fastapi import FastAPI
from models_library.function_services_catalog.api import is_function_service
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from redis.exceptions import ConnectionError as RedisConnectionError
from respx.router import MockRouter
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
