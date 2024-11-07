# pylint: disable=W0613, W0621
# pylint: disable=unused-variable

import json
import time

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director import registry_proxy


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


async def test_registry_caching(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=1, number_of_interactive_services=1
    )
    # TODO: use monkeypatching
    # config.DIRECTOR_REGISTRY_CACHING = True
    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_without_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_with_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    assert time_to_retrieve_with_cache < time_to_retrieve_without_cache


@pytest.mark.skip(reason="test needs credentials to real registry")
async def test_get_services_performance(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
):
    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    stop_time = time.perf_counter()
    print(
        f"\nTime to run getting services: {stop_time - start_time}s, #services {len(services)}, time per call {(stop_time - start_time) / len(services)}s/service"
    )


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
