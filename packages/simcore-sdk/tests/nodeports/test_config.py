
#pylint: disable=C0111
#pylint: disable=W0621
import pytest
from simcore_sdk.nodeports import config as portconfig
@pytest.fixture(scope="module",
                params=[portconfig.Location.FILE, portconfig.Location.DATABASE])
def config_location(request):
    yield request.param

def test_default_configuration(config_location):
    
    config = portconfig.CONFIG["default"]    
    config.LOCATION = config_location

def test_development_configuration(config_location):
    config = portconfig.CONFIG["development"]
    config.LOCATION = config_location

def test_production_configuration(config_location):
    config = portconfig.CONFIG["production"]
    config.LOCATION = config_location
