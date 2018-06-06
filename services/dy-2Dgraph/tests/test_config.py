
#pylint: disable=C0111
#pylint: disable=W0621
import pytest
import simcoreapi.config
@pytest.fixture(scope="module",
                params=[simcoreapi.config.Location.FILE])#, simcoreapi.config.Location.DATABASE])
def config_location(request):
    yield request.param

def test_default_configuration(config_location):
    
    config = simcoreapi.config.CONFIG["default"]    
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None

def test_development_configuration(config_location):
    config = simcoreapi.config.CONFIG["development"]
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None

def test_production_configuration(config_location):
    config = simcoreapi.config.CONFIG["production"]
    config.LOCATION = config_location
    default_file_json_configuration = config.get_ports_configuration()
    assert default_file_json_configuration is not None
