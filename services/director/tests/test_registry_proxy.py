import pytest
from simcore_service_director import (
    config,
    registry_proxy    
    )
from simcore_service_director.exceptions import DirectorException


def test_setup_registry_connection():
    config.REGISTRY_AUTH = True
    with pytest.raises(DirectorException, message="expecting missing user credential") as excinfo:
        registry_proxy.setup_registry_connection()
    config.REGISTRY_USER = "LeeVanCleef"
    with pytest.raises(DirectorException, message="expecting missing user password") as excinfo:
        registry_proxy.setup_registry_connection()
    config.REGISTRY_PW = "TheUgly"
    registry_proxy.setup_registry_connection()

def test_list_computational_services():
    pass

def test_list_interactive_services():
    pass

def test_retrieve_list_of_images_in_repo():
    pass

def test_list_interactive_service_dependencies():
    pass

def test_retrieve_labels_of_image():
    pass

def test_get_service_name():
    pass
def test_get_interactive_service_sub_name():
    pass
