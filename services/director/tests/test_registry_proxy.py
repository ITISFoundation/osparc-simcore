# pylint: disable=W0613, W0621

import pytest
from simcore_service_director import (
    config,
    registry_proxy    
    )
from simcore_service_director.exceptions import DirectorException

def test_setup_registry_connection():
    config.REGISTRY_AUTH = False
    try:
        registry_proxy.setup_registry_connection()
    except DirectorException:
        pytest.fail("Unexpected error")

    config.REGISTRY_AUTH = True
    with pytest.raises(DirectorException, message="expecting missing user credential"):
        registry_proxy.setup_registry_connection()
    config.REGISTRY_USER = "LeeVanCleef"
    with pytest.raises(DirectorException, message="expecting missing user password"):
        registry_proxy.setup_registry_connection()
    config.REGISTRY_PW = "TheUgly"
    registry_proxy.setup_registry_connection()

def test_list_no_services_available(docker_registry, configure_registry_access):    
    computational_services = registry_proxy.list_computational_services()
    assert (not computational_services) # it's empty
    interactive_services = registry_proxy.list_interactive_services()
    assert (not interactive_services)

def test_list_computational_services(docker_registry, push_services, configure_registry_access):
    push_services(6, 3)    
    computational_services = registry_proxy.list_computational_services()
    assert len(computational_services) == 6

def test_list_interactive_services(docker_registry, push_services, configure_registry_access):
    push_services(5, 4)    
    interactive_services = registry_proxy.list_interactive_services()
    assert len(interactive_services) == 4

def test_retrieve_list_of_images_in_repo(docker_registry, push_services, configure_registry_access):
    images = push_services(5, 3)
    image_number = {}
    for image in images:
        service_description = image["service_description"]
        key = service_description["key"]
        if key not in image_number:
            image_number[key] = 0
        image_number[key] = image_number[key]+1
    
    for key, number in image_number.items():
        list_of_images = registry_proxy.retrieve_list_of_images_in_repo(key)
        assert len(list_of_images["tags"]) == number

@pytest.mark.skip(reason="SAN: this must be changed according to issue #222")
def test_list_interactive_service_dependencies():
    # need to setup a fake registry to test this
    pass

def test_retrieve_labels_of_image(docker_registry, push_services, configure_registry_access):
    images = push_services(1, 1)    
    for image in images:
        service_description = image["service_description"]
        labels = registry_proxy.retrieve_labels_of_image(service_description["key"], service_description["version"])
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

def test_get_service_details(push_services, configure_registry_access):
    images = push_services(1, 1)    
    for image in images:
        service_description = image["service_description"]
        details = registry_proxy.get_service_details(service_description["key"], service_description["version"])

        assert details == service_description