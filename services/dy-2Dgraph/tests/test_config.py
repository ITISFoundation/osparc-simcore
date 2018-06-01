
#pylint: disable=C0111
import pytest
import simcore_api.config
@pytest.fixture(scope="module",
                params=[simcore_api.config.Location.FILE])#, simcore_api.config.Location.DATABASE])
def config_location(request):
    yield request.param

def test_default_configuration(config_location):
    
    config = simcore_api.config.CONFIG["default"]    
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None

def test_development_configuration(config_location):
    config = simcore_api.config.CONFIG["development"]
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None

def test_production_configuration(config_location):
    config = simcore_api.config.CONFIG["production"]
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None
