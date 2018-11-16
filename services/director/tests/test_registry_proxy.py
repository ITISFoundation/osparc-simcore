# pylint: disable=W0613, W0621

import json

import pytest

from simcore_service_director import registry_proxy


@pytest.mark.asyncio
async def test_list_no_services_available(docker_registry, configure_registry_access):    
    computational_services = await registry_proxy.list_computational_services()
    assert (not computational_services) # it's empty
    interactive_services = await registry_proxy.list_interactive_services()
    assert (not interactive_services)

@pytest.mark.asyncio
async def test_list_computational_services(docker_registry, push_services, configure_registry_access):
    push_services(6, 3)    
    computational_services = await registry_proxy.list_computational_services()
    assert len(computational_services) == 6

@pytest.mark.asyncio
async def test_list_interactive_services(docker_registry, push_services, configure_registry_access):
    push_services(5, 4)    
    interactive_services = await registry_proxy.list_interactive_services()
    assert len(interactive_services) == 4

@pytest.mark.asyncio
async def test_retrieve_list_of_images_in_repo(docker_registry, push_services, configure_registry_access):
    images = push_services(5, 3)
    image_number = {}
    for image in images:
        service_description = image["service_description"]
        key = service_description["key"]
        if key not in image_number:
            image_number[key] = 0
        image_number[key] = image_number[key]+1
    
    for key, number in image_number.items():
        list_of_images = await registry_proxy.retrieve_list_of_images_in_repo(key)
        assert len(list_of_images["tags"]) == number

@pytest.mark.asyncio
async def test_list_interactive_service_dependencies(docker_registry, push_services, configure_registry_access):
    images = push_services(2,2, inter_dependent_services=True)
    for image in images:
        service_description = image["service_description"]
        docker_labels = image["docker_labels"]
        if "simcore.service.dependencies" in docker_labels:
            docker_dependencies = json.loads(docker_labels["simcore.service.dependencies"])
            image_dependencies = await registry_proxy.list_interactive_service_dependencies(service_description["key"], service_description["version"])
            assert isinstance(image_dependencies, list)
            assert len(image_dependencies) == len(docker_dependencies)
            assert image_dependencies[0]["key"] == docker_dependencies[0]["key"]
            assert image_dependencies[0]["tag"] == docker_dependencies[0]["tag"]


@pytest.mark.asyncio
async def test_retrieve_labels_of_image(docker_registry, push_services, configure_registry_access):
    images = push_services(1, 1)    
    for image in images:
        service_description = image["service_description"]
        labels = await registry_proxy.retrieve_labels_of_image(service_description["key"], service_description["version"])
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
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler_my-sub-modeler"
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

@pytest.mark.asyncio
async def test_get_service_details(push_services, configure_registry_access):
    images = push_services(1, 1)    
    for image in images:
        service_description = image["service_description"]
        details = await registry_proxy.get_service_details(service_description["key"], service_description["version"])

        assert details == service_description
