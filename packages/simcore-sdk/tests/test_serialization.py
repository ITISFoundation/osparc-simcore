# pylint: disable=W0613, W0621, C0111
import pytest

def test_default_json_decoding(default_simcore_configuration):
    from simcore_sdk.nodeports import PORTS

    assert len(PORTS.inputs) == 2
    assert PORTS.inputs[0].key == "in_1"
    assert PORTS.inputs[0].label == "computational data"
    assert PORTS.inputs[0].description == "these are computed data out of a pipeline"
    assert PORTS.inputs[0].type == "file-url"
    assert PORTS.inputs[0].value == "/home/jovyan/data/outputControllerOut.dat"
    assert PORTS.inputs[0].timestamp == "2018-05-23T15:34:53.511Z"

    assert PORTS.inputs[1].key == "in_5"
    assert PORTS.inputs[1].label == "some number"
    assert PORTS.inputs[1].description == "numbering things"
    assert PORTS.inputs[1].type == "int"
    assert PORTS.inputs[1].value == "666"
    assert PORTS.inputs[1].timestamp == "2018-05-23T15:34:53.511Z"

    assert len(PORTS.outputs) == 1
    assert PORTS.outputs[0].key == "out_1"
    assert PORTS.outputs[0].label == "some boolean output"
    assert PORTS.outputs[0].description == "could be true or false..."
    assert PORTS.outputs[0].type == "bool"
    assert PORTS.outputs[0].value == "null"
    assert PORTS.outputs[0].timestamp == "2018-05-23T15:34:53.511Z"

def test_default_json_encoding(default_simcore_configuration): 
    from simcore_sdk.nodeports import PORTS
    from simcore_sdk.nodeports.serialization import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(PORTS, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../src/simcore_sdk/config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)

def test_wrong_version(special_simcore_configuration):
    import helpers
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    #change version to a different one
    special_configuration["version"] = "0.0"
    special_simcore_configuration(special_configuration)

    from simcore_sdk.nodeports import exceptions    
    with pytest.raises(exceptions.WrongProtocolVersionError, message="Expecting WrongProtocolVersionError") as excinfo:
        from simcore_sdk.nodeports import PORTS
        print(PORTS.inputs)
    assert "Expecting version 0.1, found version 0.0" in str(excinfo.value)

def test_invalid_configuration(special_simcore_configuration):
    special_configuration = {"whatever":"stuff"}
    special_simcore_configuration(special_configuration)

    from simcore_sdk.nodeports import exceptions
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting WrongProtocol") as excinfo:
        from simcore_sdk.nodeports import PORTS
        print(PORTS.inputs)
    assert "Invalid protocol used in" in str(excinfo.value)

def test_noinputsoutputs(special_simcore_configuration):
    # create empty configuration
    import helpers
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    special_simcore_configuration(special_configuration)

    from simcore_sdk.nodeports import PORTS
    from simcore_sdk.nodeports import exceptions

    assert not PORTS.inputs
    assert not PORTS.outputs

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        input0 = PORTS.inputs[0]
        print(input0)
    assert "No port bound at index" in str(excinfo.value)

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        output0 = PORTS.outputs[0]
        print(output0)
    assert "No port bound at index" in str(excinfo.value)
