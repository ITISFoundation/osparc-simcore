# pylint: disable=W0613, W0621
# pylint: disable=unused-variable

import asyncio
import json
import time
from unittest import mock

import pytest
from fastapi import FastAPI
from pytest_benchmark.plugin import BenchmarkFixture
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings
from simcore_service_director import registry_proxy
from simcore_service_director.core.settings import ApplicationSettings


async def test_list_no_services_available(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
):

    computational_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.COMPUTATIONAL
    )
    assert not computational_services  # it's empty
    interactive_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.DYNAMIC
    )
    assert not interactive_services
    all_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.ALL
    )
    assert not all_services


async def test_list_computational_services(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(
        number_of_computational_services=6, number_of_interactive_services=3
    )

    computational_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.COMPUTATIONAL
    )
    assert len(computational_services) == 6


async def test_list_interactive_services(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(
        number_of_computational_services=5, number_of_interactive_services=4
    )
    interactive_services = await registry_proxy.list_services(
        app, registry_proxy.ServiceType.DYNAMIC
    )
    assert len(interactive_services) == 4


async def test_list_of_image_tags(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=5, number_of_interactive_services=3
    )
    image_number = {}
    for image in images:
        service_description = image["service_description"]
        key = service_description["key"]
        if key not in image_number:
            image_number[key] = 0
        image_number[key] = image_number[key] + 1

    for key, number in image_number.items():
        list_of_image_tags = await registry_proxy.list_image_tags(app, key)
        assert len(list_of_image_tags) == number


async def test_list_interactive_service_dependencies(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=2,
        number_of_interactive_services=2,
        inter_dependent_services=True,
    )
    for image in images:
        service_description = image["service_description"]
        docker_labels = image["docker_labels"]
        if "simcore.service.dependencies" in docker_labels:
            docker_dependencies = json.loads(
                docker_labels["simcore.service.dependencies"]
            )
            image_dependencies = (
                await registry_proxy.list_interactive_service_dependencies(
                    app,
                    service_description["key"],
                    service_description["version"],
                )
            )
            assert isinstance(image_dependencies, list)
            assert len(image_dependencies) == len(docker_dependencies)
            assert image_dependencies[0]["key"] == docker_dependencies[0]["key"]
            assert image_dependencies[0]["tag"] == docker_dependencies[0]["tag"]


async def test_get_image_labels(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=1, number_of_interactive_services=1
    )
    images_digests = set()
    for image in images:
        service_description = image["service_description"]
        labels, image_manifest_digest = await registry_proxy.get_image_labels(
            app, service_description["key"], service_description["version"]
        )
        assert "io.simcore.key" in labels
        assert "io.simcore.version" in labels
        assert "io.simcore.type" in labels
        assert "io.simcore.name" in labels
        assert "io.simcore.description" in labels
        assert "io.simcore.authors" in labels
        assert "io.simcore.contact" in labels
        assert "io.simcore.inputs" in labels
        assert "io.simcore.outputs" in labels
        if service_description["type"] == "dynamic":
            # dynamic services have this additional flag
            assert "simcore.service.settings" in labels

        assert image_manifest_digest == await registry_proxy.get_image_digest(
            app, service_description["key"], service_description["version"]
        )
        assert image_manifest_digest is not None
        assert image_manifest_digest not in images_digests
        images_digests.add(image_manifest_digest)


def test_get_service_first_name():
    repo = "simcore/services/dynamic/myservice/modeler/my-sub-modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/dynamic/myservice/modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/dynamic/myservice"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice/modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice/modeler/blahblahblah"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp"
    assert registry_proxy.get_service_first_name(repo) == "invalid service"

    repo = "services/myservice/modeler/my-sub-modeler"
    assert registry_proxy.get_service_first_name(repo) == "invalid service"


def test_get_service_last_namess():
    repo = "simcore/services/dynamic/myservice/modeler/my-sub-modeler"
    assert (
        registry_proxy.get_service_last_names(repo)
        == "myservice_modeler_my-sub-modeler"
    )
    repo = "simcore/services/dynamic/myservice/modeler"
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler"
    repo = "simcore/services/dynamic/myservice"
    assert registry_proxy.get_service_last_names(repo) == "myservice"
    repo = "simcore/services/dynamic"
    assert registry_proxy.get_service_last_names(repo) == "invalid service"
    repo = "simcore/services/comp/myservice/modeler"
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler"
    repo = "services/dynamic/modeler"
    assert registry_proxy.get_service_last_names(repo) == "invalid service"


async def test_get_image_details(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=1, number_of_interactive_services=1
    )
    for image in images:
        service_description = image["service_description"]
        details = await registry_proxy.get_image_details(
            app, service_description["key"], service_description["version"]
        )

        assert details.pop("image_digest").startswith("sha")

        assert details == service_description


async def test_list_services(
    configure_registry_access: EnvVarsDict,
    configure_number_concurrency_calls: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(
        number_of_computational_services=21, number_of_interactive_services=21
    )
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    assert len(services) == 42


@pytest.fixture
def configure_registry_caching(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, {"DIRECTOR_REGISTRY_CACHING": True}
    )


@pytest.fixture
def with_disabled_auto_caching(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director.registry_proxy._list_all_services_task", autospec=True
    )


async def test_registry_caching(
    configure_registry_access: EnvVarsDict,
    configure_registry_caching: EnvVarsDict,
    with_disabled_auto_caching: mock.Mock,
    app_settings: ApplicationSettings,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=201, number_of_interactive_services=201
    )
    assert app_settings.DIRECTOR_REGISTRY_CACHING is True

    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_without_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_with_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    assert time_to_retrieve_with_cache < time_to_retrieve_without_cache
    print("time to retrieve services without cache: ", time_to_retrieve_without_cache)
    print("time to retrieve services with cache: ", time_to_retrieve_with_cache)


@pytest.fixture
def configure_number_concurrency_calls(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS": "50",
            "DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS": "50",
        },
    )


def test_list_services_performance(
    skip_if_external_envfile_dict: None,
    configure_external_registry_access: EnvVarsDict,
    configure_number_concurrency_calls: EnvVarsDict,
    registry_settings: RegistrySettings,
    app: FastAPI,
    benchmark: BenchmarkFixture,
):
    async def _list_services():
        start_time = time.perf_counter()
        services = await registry_proxy.list_services(
            app, registry_proxy.ServiceType.ALL
        )
        stop_time = time.perf_counter()
        print(
            f"\nTime to list services: {stop_time - start_time:.3}s, {len(services)} services in {registry_settings.resolved_registry_url}, rate: {(stop_time - start_time) / len(services or [1]):.3}s/service"
        )

    def run_async_test() -> None:
        asyncio.get_event_loop().run_until_complete(_list_services())

    benchmark.pedantic(run_async_test, rounds=5)


async def test_generate_service_extras(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=1, number_of_interactive_services=1
    )

    for image in images:
        service_description = image["service_description"]
        service_extras = image["service_extras"]

        extras = await registry_proxy.get_service_extras(
            app, service_description["key"], service_description["version"]
        )

        assert extras == service_extras
