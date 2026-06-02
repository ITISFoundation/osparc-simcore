# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
import toolz
from fastapi import FastAPI
from models_library.function_services_catalog.api import is_function_service
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
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


async def test_get_batch_services_returns_keyerror_for_missing(
    director_client: DirectorClient,
):
    selection = [("simcore/services/comp/does-not-exist", "1.0.0")]

    got_services = await manifest.get_batch_services(selection, director_client)

    assert len(got_services) == 1
    assert isinstance(got_services[0], KeyError)
