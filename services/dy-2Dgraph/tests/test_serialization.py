# pylint: disable=W0613, W0621, C0111
import pytest

def test_default_json_encoding(default_simcore_configuration): 
    from simcore_api import PORTS
    from simcore_api.serialization import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(PORTS, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)

def test_wrong_version(special_simcore_configuration):
    import helpers
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    #change version to a different one
    special_configuration["version"] = "0.0"
    special_simcore_configuration(special_configuration)

    from simcore_api import exceptions    
    with pytest.raises(exceptions.WrongProtocolVersionError, message="Expecting WrongProtocolVersionError") as excinfo:
        from simcore_api import PORTS
        print(PORTS.inputs)
    assert "Expecting version 0.1, found version 0.0" in str(excinfo.value)

def test_invalid_configuration(special_simcore_configuration):
    special_configuration = {"whatever":"stuff"}
    special_simcore_configuration(special_configuration)

    from simcore_api import exceptions
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting WrongProtocol") as excinfo:
        from simcore_api import PORTS
        print(PORTS.inputs)
    assert "Invalid protocol used in" in str(excinfo.value)
